import json

from esg_reliable_discovery.config import ModelConfig


def test_model_config_round_trip(tmp_path):
    path = tmp_path / "model.json"
    path.write_text(
        json.dumps(
            {
                "provider": "ollama",
                "deployment": "local",
                "base_url": "http://localhost:11434/api",
                "model": "test-model",
            }
        )
    )
    config = ModelConfig.from_path(path)
    assert config.model == "test-model"
    assert config.options == {}
    assert "api_key_env" in config.public_dict()
