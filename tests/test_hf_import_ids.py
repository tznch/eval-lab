from shared.hf_import.ids import (
    default_dataset_id_from_hf,
    default_model_id_from_repo,
    sanitize_local_id,
)


def test_sanitize_rejects_traversal():
    assert sanitize_local_id("../etc") == "etc"
    assert sanitize_local_id("") == "import"
    assert sanitize_local_id("_template") == "template"


def test_defaults_from_repo_paths():
    assert default_model_id_from_repo("org/My-Model-GGUF") == "my-model-gguf"
    assert default_dataset_id_from_hf("allenai/sciq") == "sciq"
