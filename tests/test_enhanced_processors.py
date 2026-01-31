"""
Tests for enhanced validators and transformers.

Tests:
- New validators (RangeValidator, NotEmptyValidator, etc.)
- New transformers (ClampTransformer, SlugifyTransformer, etc.)
- Edge cases and complex usage patterns
"""

import pytest
from typing import List

from foobara_py.types import (
    FoobaraType,
    StringType,
    IntegerType,
    FloatType,
    # New validators
    RangeValidator,
    NotEmptyValidator,
    UniqueItemsValidator,
    ContainsValidator,
    # New transformers
    ClampTransformer,
    DefaultTransformer,
    TruncateTransformer,
    SlugifyTransformer,
    NormalizeWhitespaceTransformer,
    # Casters
    StringCaster,
    IntegerCaster,
    FloatCaster,
    ListCaster,
)


class TestNewValidators:
    """Test new validator implementations"""

    def test_range_validator_integers(self):
        """Test RangeValidator with integers"""
        validator = RangeValidator(0, 100)

        assert validator.process(0) == 0
        assert validator.process(50) == 50
        assert validator.process(100) == 100

        with pytest.raises(ValueError, match='between 0 and 100'):
            validator.process(-1)

        with pytest.raises(ValueError, match='between 0 and 100'):
            validator.process(101)

    def test_range_validator_floats(self):
        """Test RangeValidator with floats"""
        validator = RangeValidator(0.0, 1.0)

        assert validator.process(0.0) == 0.0
        assert validator.process(0.5) == 0.5
        assert validator.process(1.0) == 1.0

        with pytest.raises(ValueError):
            validator.process(-0.1)

        with pytest.raises(ValueError):
            validator.process(1.1)

    def test_not_empty_validator_string(self):
        """Test NotEmptyValidator with strings"""
        validator = NotEmptyValidator()

        assert validator.process('hello') == 'hello'
        assert validator.process(' ') == ' '  # Whitespace is not empty

        with pytest.raises(ValueError, match='cannot be empty'):
            validator.process('')

    def test_not_empty_validator_list(self):
        """Test NotEmptyValidator with lists"""
        validator = NotEmptyValidator()

        assert validator.process([1, 2, 3]) == [1, 2, 3]
        assert validator.process([1]) == [1]

        with pytest.raises(ValueError, match='cannot be empty'):
            validator.process([])

    def test_not_empty_validator_dict(self):
        """Test NotEmptyValidator with dicts"""
        validator = NotEmptyValidator()

        assert validator.process({'key': 'value'}) == {'key': 'value'}

        with pytest.raises(ValueError, match='cannot be empty'):
            validator.process({})

    def test_not_empty_validator_set(self):
        """Test NotEmptyValidator with sets"""
        validator = NotEmptyValidator()

        assert validator.process({1, 2, 3}) == {1, 2, 3}

        with pytest.raises(ValueError, match='cannot be empty'):
            validator.process(set())

    def test_unique_items_validator(self):
        """Test UniqueItemsValidator"""
        validator = UniqueItemsValidator()

        # All unique items
        assert validator.process([1, 2, 3]) == [1, 2, 3]
        assert validator.process(['a', 'b', 'c']) == ['a', 'b', 'c']
        assert validator.process([]) == []

        # Duplicate items should fail
        with pytest.raises(ValueError, match='must be unique'):
            validator.process([1, 2, 2, 3])

        with pytest.raises(ValueError, match='must be unique'):
            validator.process(['a', 'b', 'a'])

    def test_contains_validator_case_sensitive(self):
        """Test ContainsValidator with case sensitivity"""
        validator = ContainsValidator('@', case_sensitive=True)

        assert validator.process('user@example.com') == 'user@example.com'
        assert validator.process('test@test') == 'test@test'

        with pytest.raises(ValueError, match="must contain '@'"):
            validator.process('username')

    def test_contains_validator_case_insensitive(self):
        """Test ContainsValidator case insensitive"""
        validator = ContainsValidator('HELLO', case_sensitive=False)

        assert validator.process('hello world') == 'hello world'
        assert validator.process('HELLO WORLD') == 'HELLO WORLD'
        assert validator.process('Say hello!') == 'Say hello!'

        with pytest.raises(ValueError, match="must contain 'HELLO'"):
            validator.process('goodbye')

    def test_contains_validator_substring(self):
        """Test ContainsValidator with various substrings"""
        validator = ContainsValidator('test')

        assert validator.process('testing') == 'testing'
        assert validator.process('test') == 'test'
        assert validator.process('latest') == 'latest'

        with pytest.raises(ValueError):
            validator.process('hello')


class TestNewTransformers:
    """Test new transformer implementations"""

    def test_clamp_transformer_integers(self):
        """Test ClampTransformer with integers"""
        transformer = ClampTransformer(0, 100)

        # Within range
        assert transformer.process(50) == 50
        assert transformer.process(0) == 0
        assert transformer.process(100) == 100

        # Below range
        assert transformer.process(-10) == 0
        assert transformer.process(-1) == 0

        # Above range
        assert transformer.process(101) == 100
        assert transformer.process(200) == 100

    def test_clamp_transformer_floats(self):
        """Test ClampTransformer with floats"""
        transformer = ClampTransformer(0.0, 1.0)

        assert transformer.process(0.5) == 0.5
        assert transformer.process(-0.5) == 0.0
        assert transformer.process(1.5) == 1.0

    def test_default_transformer_none(self):
        """Test DefaultTransformer with None values"""
        transformer = DefaultTransformer('default_value')

        assert transformer.process(None) == 'default_value'
        assert transformer.process('actual_value') == 'actual_value'

    def test_default_transformer_empty_string(self):
        """Test DefaultTransformer with empty strings"""
        transformer = DefaultTransformer('default', replace_empty=True)

        assert transformer.process('') == 'default'
        assert transformer.process(None) == 'default'
        assert transformer.process('value') == 'value'

    def test_default_transformer_no_replace_empty(self):
        """Test DefaultTransformer without empty replacement"""
        transformer = DefaultTransformer('default', replace_empty=False)

        assert transformer.process(None) == 'default'
        assert transformer.process('') == ''  # Empty not replaced
        assert transformer.process('value') == 'value'

    def test_default_transformer_with_list(self):
        """Test DefaultTransformer with list default"""
        transformer = DefaultTransformer([])

        assert transformer.process(None) == []
        assert transformer.process([1, 2, 3]) == [1, 2, 3]

    def test_truncate_transformer_short_string(self):
        """Test TruncateTransformer with short strings"""
        transformer = TruncateTransformer(10)

        # String shorter than max - no truncation
        assert transformer.process('hello') == 'hello'
        assert transformer.process('hi') == 'hi'

    def test_truncate_transformer_long_string(self):
        """Test TruncateTransformer with long strings"""
        transformer = TruncateTransformer(10, suffix='...')

        # String longer than max - truncate with suffix
        assert transformer.process('hello world!') == 'hello w...'
        assert len(transformer.process('hello world!')) == 10

    def test_truncate_transformer_custom_suffix(self):
        """Test TruncateTransformer with custom suffix"""
        transformer = TruncateTransformer(10, suffix='→')

        result = transformer.process('hello world!')
        assert len(result) == 10
        assert result.endswith('→')
        assert result == 'hello wor→'

    def test_slugify_transformer_basic(self):
        """Test SlugifyTransformer basic functionality"""
        transformer = SlugifyTransformer()

        assert transformer.process('Hello World') == 'hello-world'
        assert transformer.process('Test String') == 'test-string'

    def test_slugify_transformer_special_chars(self):
        """Test SlugifyTransformer removes special characters"""
        transformer = SlugifyTransformer()

        assert transformer.process('Hello World!') == 'hello-world'
        assert transformer.process('Test@#$String') == 'teststring'
        assert transformer.process('Product #123') == 'product-123'

    def test_slugify_transformer_whitespace(self):
        """Test SlugifyTransformer handles whitespace"""
        transformer = SlugifyTransformer()

        assert transformer.process('  hello  world  ') == 'hello-world'
        assert transformer.process('multiple   spaces') == 'multiple-spaces'

    def test_slugify_transformer_hyphens(self):
        """Test SlugifyTransformer handles hyphens"""
        transformer = SlugifyTransformer()

        assert transformer.process('already-a-slug') == 'already-a-slug'
        assert transformer.process('multiple---hyphens') == 'multiple-hyphens'
        assert transformer.process('-leading-trailing-') == 'leading-trailing'

    def test_normalize_whitespace_transformer(self):
        """Test NormalizeWhitespaceTransformer"""
        transformer = NormalizeWhitespaceTransformer()

        # Multiple spaces
        assert transformer.process('hello    world') == 'hello world'

        # Leading/trailing spaces
        assert transformer.process('  hello  ') == 'hello'

        # Mixed whitespace (tabs, newlines, etc.)
        assert transformer.process('hello\t\nworld') == 'hello world'

        # Already normalized
        assert transformer.process('hello world') == 'hello world'


class TestEnhancedTypeCreation:
    """Test creating types with new validators and transformers"""

    def test_bounded_integer_type(self):
        """Test creating bounded integer type with RangeValidator"""
        score_type = FoobaraType(
            name='score',
            python_type=int,
            casters=[IntegerCaster()],
            validators=[RangeValidator(0, 100)],
            description='Score between 0 and 100'
        )

        assert score_type.process('50') == 50
        assert score_type.process('0') == 0
        assert score_type.process('100') == 100

        with pytest.raises(ValueError):
            score_type.process('-1')

        with pytest.raises(ValueError):
            score_type.process('101')

    def test_clamped_float_type(self):
        """Test creating type with ClampTransformer"""
        normalized_type = FoobaraType(
            name='normalized',
            python_type=float,
            casters=[FloatCaster()],
            transformers=[ClampTransformer(0.0, 1.0)],
            description='Value clamped to [0, 1]'
        )

        assert normalized_type.process('0.5') == 0.5
        assert normalized_type.process('-0.5') == 0.0  # Clamped to 0
        assert normalized_type.process('1.5') == 1.0  # Clamped to 1

    def test_slug_type(self):
        """Test creating slug type with transformers"""
        slug_type = FoobaraType(
            name='slug',
            python_type=str,
            casters=[StringCaster()],
            transformers=[SlugifyTransformer()],
            validators=[NotEmptyValidator()],
            description='URL-safe slug'
        )

        assert slug_type.process('Hello World!') == 'hello-world'
        assert slug_type.process('Product #123') == 'product-123'

        with pytest.raises(ValueError, match='cannot be empty'):
            slug_type.process('!!!')  # All special chars removed -> empty

    def test_required_list_type(self):
        """Test creating required list type"""
        tags_type = FoobaraType(
            name='tags',
            python_type=list,
            casters=[ListCaster()],
            validators=[NotEmptyValidator(), UniqueItemsValidator()],
            description='Non-empty list of unique tags'
        )

        assert tags_type.process(['tag1', 'tag2', 'tag3']) == ['tag1', 'tag2', 'tag3']
        assert tags_type.process('tag1,tag2') == ['tag1', 'tag2']

        with pytest.raises(ValueError, match='cannot be empty'):
            tags_type.process([])

        with pytest.raises(ValueError, match='must be unique'):
            tags_type.process(['tag1', 'tag2', 'tag1'])

    def test_normalized_string_type(self):
        """Test creating normalized string type"""
        text_type = FoobaraType(
            name='text',
            python_type=str,
            casters=[StringCaster()],
            transformers=[NormalizeWhitespaceTransformer()],
            validators=[NotEmptyValidator()],
            description='Text with normalized whitespace'
        )

        assert text_type.process('hello    world') == 'hello world'
        assert text_type.process('  text  ') == 'text'

        with pytest.raises(ValueError, match='cannot be empty'):
            text_type.process('   ')  # Only whitespace -> empty after normalization

    def test_email_with_domain_validation(self):
        """Test email type with domain validation"""
        from foobara_py.types import EmailValidator, LowercaseTransformer, StripWhitespaceTransformer

        work_email_type = FoobaraType(
            name='work_email',
            python_type=str,
            casters=[StringCaster()],
            transformers=[StripWhitespaceTransformer(), LowercaseTransformer()],
            validators=[
                EmailValidator(),
                ContainsValidator('@company.com', case_sensitive=False)
            ],
            description='Company email address'
        )

        assert work_email_type.process('  USER@COMPANY.COM  ') == 'user@company.com'

        with pytest.raises(ValueError, match="must contain '@company.com'"):
            work_email_type.process('user@gmail.com')


class TestComplexProcessingPipelines:
    """Test complex processing pipelines with new processors"""

    def test_slug_with_truncation(self):
        """Test slug creation with truncation"""
        short_slug_type = FoobaraType(
            name='short_slug',
            python_type=str,
            casters=[StringCaster()],
            transformers=[
                SlugifyTransformer(),
                TruncateTransformer(20, suffix='')  # No suffix for slugs
            ],
            description='Short URL slug'
        )

        # Short enough - no truncation
        assert short_slug_type.process('Hello World') == 'hello-world'

        # Too long - truncate
        result = short_slug_type.process('This Is A Very Long Product Title That Needs Truncation')
        assert len(result) <= 20
        assert result.islower()
        assert ' ' not in result

    def test_score_with_clamping_and_validation(self):
        """Test score type with both clamping and validation"""
        # First clamp to valid range, then validate
        score_type = FoobaraType(
            name='score',
            python_type=int,
            casters=[IntegerCaster()],
            transformers=[ClampTransformer(0, 100)],
            validators=[RangeValidator(0, 100)],  # Should always pass after clamping
            description='Score clamped to 0-100'
        )

        assert score_type.process('50') == 50
        assert score_type.process('-10') == 0  # Clamped
        assert score_type.process('150') == 100  # Clamped

        # All values pass validation because they're clamped first

    def test_list_with_element_validation(self):
        """Test list type with element-level validation"""
        positive_ints_type = FoobaraType(
            name='positive_ints',
            python_type=int,
            casters=[IntegerCaster()],
            validators=[RangeValidator(1, 1000)]
        )

        positive_list_type = positive_ints_type.array()

        # All valid
        result = positive_list_type.process(['1', '10', '100'])
        assert result == [1, 10, 100]

        # Contains invalid element
        with pytest.raises(ValueError):
            positive_list_type.process(['1', '0', '10'])  # 0 not in range

        with pytest.raises(ValueError):
            positive_list_type.process(['1', '1001', '10'])  # 1001 out of range

    def test_default_with_transformation(self):
        """Test default value with transformation"""
        status_type = FoobaraType(
            name='status',
            python_type=str,
            transformers=[
                DefaultTransformer('active', replace_empty=True),
                NormalizeWhitespaceTransformer()
            ],
            description='Status with default'
        )

        assert status_type.process(None) == 'active'
        assert status_type.process('') == 'active'
        assert status_type.process('  pending  ') == 'pending'
        assert status_type.process('in    progress') == 'in progress'


class TestEdgeCases:
    """Test edge cases with new processors"""

    def test_clamp_with_equal_bounds(self):
        """Test ClampTransformer with min == max"""
        transformer = ClampTransformer(5, 5)

        # All values should become 5
        assert transformer.process(0) == 5
        assert transformer.process(5) == 5
        assert transformer.process(10) == 5

    def test_truncate_with_long_suffix(self):
        """Test TruncateTransformer when suffix is longer than max_length"""
        transformer = TruncateTransformer(5, suffix='...')

        # Suffix is 3 chars, max is 5, so only 2 chars + suffix
        result = transformer.process('Hello World')
        assert len(result) == 5
        assert result == 'He...'

    def test_slugify_empty_result(self):
        """Test SlugifyTransformer when all chars are removed"""
        transformer = SlugifyTransformer()

        # Only special characters - results in empty string
        assert transformer.process('!!!') == ''
        assert transformer.process('@#$%') == ''

    def test_unique_items_with_non_hashable(self):
        """Test UniqueItemsValidator might fail with non-hashable items"""
        validator = UniqueItemsValidator()

        # Lists are not hashable, so this will raise when trying to create a set
        # This is expected behavior - unique validation requires hashable items
        with pytest.raises(TypeError):
            validator.process([[1, 2], [3, 4], [1, 2]])

    def test_contains_with_empty_substring(self):
        """Test ContainsValidator with empty substring"""
        validator = ContainsValidator('')

        # Empty string is contained in all strings
        assert validator.process('anything') == 'anything'
        assert validator.process('') == ''

    def test_range_validator_with_same_bounds(self):
        """Test RangeValidator when min == max"""
        validator = RangeValidator(5, 5)

        # Only 5 is valid
        assert validator.process(5) == 5

        with pytest.raises(ValueError):
            validator.process(4)

        with pytest.raises(ValueError):
            validator.process(6)
