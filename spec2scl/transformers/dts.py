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
        tail = text.splitlines(True)[1:]
        tail.append('\n%{?scl:EOF}\n')
        return ''.join(head + tail)

    @matches(r'^%license', one_line=True, sections=['%files'])
    def eliminate_license_macro(self, original_spec, pattern, text):
        return text.replace('%license', '%doc', 1)

    @matches(r'(?<!d)(Requires:\s*)(?!\w*/\w*)([^[\s]+)', sections=settings.METAINFO_SECTIONS)
    @matches(r'(BuildRequires:\s*)(?!\w*/\w*)([^\s]+)', sections=settings.METAINFO_SECTIONS)
    def handle_req_buildreq(self, original_spec, pattern, text):
        tag = text[0:text.find(':') + 1]
        deps = text[text.find(':') + 1:]

        def handle_scl_deps(args_list_file):
            scl_deps = True
            if args_list_file:
                scl_deps = []
                with open(args_list_file) as l:
                    for i in l.readlines():
                        scl_deps.append(i.strip())
            return scl_deps

        try:
            scl_deps = handle_scl_deps("/home/mbooth/DTS40/devtoolset-4-provides")
            scl_java_common_deps = handle_scl_deps("/home/mbooth/DTS40/rh-java-common-provides")
            scl_maven30_deps = handle_scl_deps("/home/mbooth/DTS40/maven30-provides")
        except IOError as e:
            print('Could not open file: {0}'.format(e))
            sys.exit(1)

        # handle more Requires on one line

        def handle_one_dep(matchobj):
            groupdict = matchobj.groupdict('')

            scl_ignored_deps = ['java-headless', 'java-devel']

            if scl_deps and groupdict['dep'] in scl_deps:
                dep = '%{{?scl_prefix}}{0}'.format(groupdict['dep'])
            elif scl_java_common_deps and groupdict['dep'] in scl_java_common_deps:
                dep = '%{{?scl_prefix_java_common}}{0}'.format(groupdict['dep'])
            elif scl_maven30_deps and groupdict['dep'] in scl_maven30_deps:
                dep = '%{{?scl_prefix_maven}}{0}'.format(groupdict['dep'])
            else:
                dep = groupdict['dep']

            if scl_ignored_deps and groupdict['dep'] in scl_ignored_deps:
                return None
            else:
                return '{0}{1}{2}{3}'.format(groupdict['prespace'], dep, groupdict['ver'], groupdict['postspace'])

        dep_re = re.compile(r'(?P<prespace>\s*)(?P<dep>([^\s]+(.+\))?))(?P<ver>\s*[<>=!]+\s*[^\s]+)?(?P<postspace>\s*)')
        new_dep = dep_re.sub(handle_one_dep, deps)
        if new_dep:
            return tag + new_dep
        else:
            return ''


