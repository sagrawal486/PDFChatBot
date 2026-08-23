from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "f2c4d6e8a1b3_add_storage_metadata_to_documents.py"
)


def test_document_migration_preserves_file_path_as_storage_key() -> None:
    migration_text = MIGRATION_PATH.read_text()

    assert "UPDATE documents SET storage_key = file_path" in migration_text
    assert 'op.drop_column("documents", "file_path")' in migration_text


def test_document_migration_adds_storage_metadata_columns() -> None:
    migration_text = MIGRATION_PATH.read_text()

    assert 'sa.Column("storage_key", sa.Text(), nullable=True)' in migration_text
    assert 'sa.Column("content_type", sa.String(length=100), nullable=True)' in migration_text
    assert 'sa.Column("file_size", sa.Integer(), nullable=True)' in migration_text
