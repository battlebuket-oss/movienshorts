import pytest
from fastapi import HTTPException

from src.content_rights import require_source_rights_confirmation


def test_explicit_true_confirmation_is_accepted():
    assert require_source_rights_confirmation(True) is None


@pytest.mark.parametrize("value", [False, None, 0, "true", "yes", {}, []])
def test_non_boolean_or_missing_confirmation_is_rejected(value):
    with pytest.raises(HTTPException) as error:
        require_source_rights_confirmation(value)

    assert error.value.status_code == 400
    assert error.value.detail["code"] == "SOURCE_RIGHTS_REQUIRED"
