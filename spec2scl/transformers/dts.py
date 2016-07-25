import re
import sys

from spec2scl.decorators import matches
from spec2scl import settings
from spec2scl import transformer

@transformer.Transformer.register_transformer
class DTSTransformer(transformer.Transformer):
    def __init__(self, options={}):
        super(DTSTransformer, self).__init__(options)

    @matches(r'^', one_line=False, sections=['%header'])
    def insert_dts_scl_init(self, original_spec, pattern, text):
        scl_init = '%{{?scl:%scl_package {0}}}\n%{{!?scl:%global pkg_name %{{name}}}}\n%{{?java_common_find_provides_and_requires}}\n'.format(self.get_original_name(original_spec))
        return '{0}\n%global baserelease 0\n\n{1}'.format(scl_init, text)

    @matches(r'^Release:', one_line=True, sections=settings.METAINFO_SECTIONS)
    def insert_baserelease(self, original_spec, pattern, text):
        return text.replace('%{?dist}', '.%{baserelease}%{?dist}', 1)

    @matches(r'^', one_line=False, sections=settings.RUNTIME_SECTIONS)
    def wrap_section_body(self, original_spec, pattern, text):
        head = text.splitlines(True)[0:1]
        head.append('%{?scl:scl enable %{scl_maven} %{scl} - << "EOF"}\n')
        head.append('set -e -x\n')
        tail = text.splitlines(True)[1:]
        tail.append('\n%{?scl:EOF}\n')
        return ''.join(head + tail)

    @matches(r'^%license', one_line=True, sections=['%files'])
    def eliminate_license_macro(self, original_spec, pattern, text):
        return text.replace('%license', '%doc', 1)

    @matches(r'(Obsoletes:\s*)(?!\w*/\w*)([^\s]+)', sections=settings.METAINFO_SECTIONS)
    @matches(r'(Provides:\s*)(?!\w*/\w*)([^\s]+)', sections=settings.METAINFO_SECTIONS)
    def handle_req_provides(self, original_spec, pattern, text):
        tag = text[0:text.find(':') + 1]
        provs = text[text.find(':') + 1:]
        # handle more Provides on one line

        def handle_one_prov(matchobj):
            groupdict = matchobj.groupdict('')
            provide = groupdict['dep']
            # prefix with scl name unless they begin with %{name} (in which case they are already prefixed)
            if not provide.startswith('%{name}'):
                provide = '%{{?scl_prefix}}{0}'.format(provide)
            return '{0}{1}{2}{3}'.format(groupdict['prespace'], provide, groupdict['ver'], groupdict['postspace'])

        prov_re = re.compile(r'(?P<prespace>\s*)(?P<dep>([^\s,]+(.+\))?))(?P<ver>\s*[<>=!]+\s*[^\s]+)?(?P<postspace>,?\s*)')
        new_prov = prov_re.sub(handle_one_prov, provs)
        if new_prov:
            return tag + new_prov
        else:
            return ''

    @matches(r'(?<!d)(Requires:\s*)(?!\w*/\w*)([^[\s]+)', sections=settings.METAINFO_SECTIONS)
    @matches(r'(BuildRequires:\s*)(?!\w*/\w*)([^\s]+)', sections=settings.METAINFO_SECTIONS)
    def handle_req_buildreq(self, original_spec, pattern, text):
        tag = text[0:text.find(':') + 1]
        deps = text[text.find(':') + 1:]
        # handle more Requires on one line

        def handle_one_dep(matchobj):
            groupdict = matchobj.groupdict('')

            # these deps are simply stripped
            scl_ignored_deps = ['java-headless', 'java-devel']
            # these are high priority maven deps (they are considered ahead of java-common deps)
            scl_hi_pri_maven_deps = ['javapackages-local', 'maven-local', 'ivy-local']
            # these deps have a different name to Fedora and must be transformed
            scl_dep_transforms = { 'antlr':'antlr-tool', 'objectweb-asm':'objectweb-asm5', 'mvn(org.ow2.asm:asm-all)':'mvn(org.ow2.asm:asm-all:5)', 'mvn(org.ow2.asm:asm)':'mvn(org.ow2.asm:asm:5)', 'mvn(org.ow2.asm:asm-analysis)':'mvn(org.ow2.asm:asm-analysis:5)', 'mvn(org.ow2.asm:asm-commons)':'mvn(org.ow2.asm:asm-commons:5)', 'mvn(org.ow2.asm:asm-tree)':'mvn(org.ow2.asm:asm-tree:5)', 'mvn(org.ow2.asm:asm-util)':'mvn(org.ow2.asm:asm-util:5)', 'mvn(org.ow2.asm:asm-xml)':'mvn(org.ow2.asm:asm-xml:5)', 'easymock':'easymock2', 'mvn(org.easymock:easymock)':'mvn(org.easymock:easymock:2.4)'}
            # collection provides lists
            scl_deps = self.options['scl_deps']
            scl_deps_maven = self.options['scl_deps_maven']
            scl_deps_java_common = self.options['scl_deps_java_common']

            # do transformation first
            transformed_dep = groupdict['dep']
            if groupdict['dep'] in list(scl_dep_transforms.keys()):
                transformed_dep = scl_dep_transforms[groupdict['dep']]

            # then add collection-specific prefixes
            if scl_deps and transformed_dep in scl_deps:
                dep = '%{{?scl_prefix}}{0}'.format(transformed_dep)
            elif scl_deps_maven and transformed_dep in scl_deps_maven and transformed_dep in scl_hi_pri_maven_deps:
                dep = '%{{?scl_prefix_maven}}{0}'.format(transformed_dep)
            elif scl_deps_java_common and transformed_dep in scl_deps_java_common:
                dep = '%{{?scl_prefix_java_common}}{0}'.format(transformed_dep)
            elif scl_deps_maven and transformed_dep in scl_deps_maven:
                dep = '%{{?scl_prefix_maven}}{0}'.format(transformed_dep)
            else:
                dep = transformed_dep

            if scl_ignored_deps and transformed_dep in scl_ignored_deps:
                return None
            else:
                return '{0}{1}{2}{3}'.format(groupdict['prespace'], dep, groupdict['ver'], groupdict['postspace'])

        dep_re = re.compile(r'(?P<prespace>\s*)(?P<dep>([^\s,]+(.+\))?))(?P<ver>\s*[<>=!]+\s*[^\s]+)?(?P<postspace>,?\s*)')
        new_dep = dep_re.sub(handle_one_dep, deps)
        if new_dep:
            return tag + new_dep
        else:
            return ''


