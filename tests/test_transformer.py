#TODO: use mocking to test functions in isolation
import itertools
import re

import pytest

from spec2scl.decorators import matches
from spec2scl.transformers.transformer import Transformer

from tests.transformer_test_case import TransformerTestCase

class SpamTransformer(Transformer):
    """This is a testing class to test various Transformer methods"""
    def __init__(self, spec, options = None):
        self.original_spec = spec
        self.scl_spec = spec
        self.options = options or {}
        self.one_line_transformers, self.more_lines_transformers = self.collect_transformer_methods()

    @matches(r'spam')
    def handle_spam(self, pattern, text):
        return text.replace('spam', 'handled spam', 1)

    @matches(r'spam\nspam', one_line = False)
    def handle_global_spam(self, pattern, text):
        return text.replace('spam\nspam', 'handled global\nspam', 1)

    @matches(r'foo')
    def handle_foo(self, pattern, text):
        return text.replace('foo', 'handled foo', 1)

    @matches(r'foo\nfoo', one_line = False)
    def handle_global_foo(self, pattern, text):
        return text.replace('foo\nfoo', 'handled global\nfoo', 1)

    @matches(r'looney', one_line = False)
    def handle_simple_global_looney(self, pattern, text):
        return self.sclize_all_commands(pattern, text)

    @matches(r'ham\s+', one_line=False)
    def handle_spam_and_space(self, pattern, text):
        return self.sclize_all_commands(pattern, text)

    # test helper attributes/methods
    # it may be needed to alter these when something is changed in this class
    _transformers_one_line = set(['handle_spam', 'handle_foo'])
    _transformers_more_lines = set(['handle_global_spam', 'handle_global_foo', 'handle_simple_global_looney', 'handle_spam_and_space'])
    _patterns_one_line = set([r'spam', r'foo'])
    _patterns_more_lines = set([r'spam\nspam', r'foo\nfoo', r'looney', r'ham\s+'])

class TestTransformer(TransformerTestCase):
    def setup_method(self, method):
        self.t = Transformer('', {})
        self.st = SpamTransformer('', {})

    # ========================= tests for methods that don't apply to Transformer subclasses

    @pytest.mark.parametrize(('spec', 'expected'), [
        ('nothing', 'TODO'),
        ('Name: foo', 'foo'),
        ('Name: foo', 'foo'),
        ('Name: %{spam}foo', '%{spam}foo'),
        ('Name: foo-_%{spam}', 'foo-_%{spam}'),
    ])
    def test_get_original_name(self, spec, expected):
        self.t.original_spec = spec
        self.t.scl_spec = 'Name: error if taken from here'
        assert self.t.get_original_name() == expected

    @pytest.mark.parametrize(('pattern', 'spec', 'expected'), [
        (re.compile(r'eat spam'), 'eat spam\neat eat spam', ['eat spam\n', 'eat eat spam']),
        (re.compile(r'eat spam'), 'spam eat\nand spam', []),
        (re.compile(r'eat spam'), 'eat spam \\\n and ham', ['eat spam \\\n and ham']),
        (re.compile(r'eat spam'), 'SPAM=SPAM eat spam', ['SPAM=SPAM eat spam']),
        (re.compile(r'eat spam'), 'SPAM=SPAM eat spam \\\n and ham', ['SPAM=SPAM eat spam \\\n and ham']),
        (re.compile(r'^spam\s+', re.MULTILINE), 'xspam\nspam ', ['spam ']),
    ])
    def test_find_whole_commands(self, pattern, spec, expected):
        assert self.t.find_whole_commands(pattern, spec) == expected

    @pytest.mark.parametrize(('command', 'expected'), [
        ('nope', False),
        ('yep\\\nyep', False),
        ('nope"', False),
        ('nope\'', False),
        ('yep"\'', True),
        ('A=a yep"\'', True),
    ])
    def test_command_needs_heredoc_for_execution(self, command, expected):
        assert self.t.command_needs_heredoc_for_execution(command) == expected

    # ========================= tests for methods that apply to Transformer subclasses

    def test_collect_transformer_methods(self):
        one_line, more_lines = self.st.collect_transformer_methods()
        # check methods
        assert set(map(lambda x: x.__name__, one_line.keys())) == self.st._transformers_one_line
        assert set(map(lambda x: x.__name__, more_lines.keys())) == self.st._transformers_more_lines
        # check patterns - the one_line.values() and more_lines.values() are list of lists -> use chain to flatten them
        # and then map them to their patterns
        assert set(map(lambda x: x.pattern, itertools.chain(*one_line.values()))) == self.st._patterns_one_line
        assert set(map(lambda x: x.pattern, itertools.chain(*more_lines.values()))) == self.st._patterns_more_lines

    @pytest.mark.parametrize(('spec', 'expected'), [
        ('nothing to do', 'nothing to do'),
        ('foo', 'handled foo'),
        ('spam', 'handled spam'),
    ])
    def test_apply_one_line_transformers(self, spec, expected):
        self.st.original_spec = spec
        self.st.scl_spec = spec
        assert self.st.apply_one_line_transformers() == expected

    @pytest.mark.parametrize(('spec', 'expected'), [
        ('foo spam', 'handled foo handled spam'),
    ])
    def test_multiple_one_line_transformers_apply_on_one_line(self, spec, expected):
        self.st.original_spec = spec
        self.st.scl_spec = spec
        assert self.st.apply_one_line_transformers() == expected

    @pytest.mark.parametrize(('spec', 'expected'), [
        ('nothing to do', 'nothing to do'),
        ('foo\nfoo', 'handled global\nfoo'),
        ('spam\nspam', 'handled global\nspam'),
        ('spam\nspam\nfoo\nfoo', 'handled global\nspam\nhandled global\nfoo'),
        ('spam\nxspam', 'spam\nxspam'),
    ])
    def test_apply_more_line_transformers(self, spec, expected):
        self.st.original_spec = spec
        self.st.scl_spec = spec
        assert self.st.apply_more_line_transformers() == expected

    @pytest.mark.parametrize(('spec', 'expected'), [
        ('looney\nlooney\n', '%{?scl:scl enable %{scl} "}\nlooney\n%{?scl:"}\n%{?scl:scl enable %{scl} "}\nlooney\n%{?scl:"}\n'),
    ])
    def test_transformers_dont_apply_scl_enable_twice(self, spec, expected):
        self.st.original_spec = spec
        self.st.scl_spec = spec
        assert self.st.apply_more_line_transformers() == expected

    def test_one_line_pattern_endswith_arbitrary_space_doesnt_hang(self):
        # if one line pattern ends with \s+, then it might match multiple \n
        # therefore it won't get found in lines.split in find_whole_commands
        # (well, it didn't, now it works)
        self.st.original_spec = 'ham\n\n'
        self.st.scl_spec = 'ham\n\n'
        self.st.apply_more_line_transformers()
        assert True # if it didn't end in endless loop, we're fine

    @pytest.mark.parametrize(('spec'), [
        ('# ham\n'),
        ('blahblah # ham\n'),
    ])
    def test_ignores_commented_commands(self, spec):
        self.t.original_spec = spec
        self.t.scl_spec = spec
        assert 'enable' not in self.t.transform()
