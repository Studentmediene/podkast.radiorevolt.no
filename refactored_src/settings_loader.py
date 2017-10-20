import os.path

import yaml

# Variables for YAML settings loader
YAML_CONFIG_FILE_ENVIRONMENT_VARIABLE = "PODCAST_YAML_FILE"
DEFAULT_YAML_CONFIG_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "..",
    "settings.yaml"
))

# Variables pertaining to the process of loading settings itself
METHOD_ENVIRONMENT_VARIABLE = "PODCAST_SETTINGS_METHOD"
DEFAULT_METHOD = "yaml"


def yaml_load_settings_from_file(configuration_file):
    with open(configuration_file) as file:
        return yaml.load(file)


def yaml_load_settings():
    default_config_file = DEFAULT_YAML_CONFIG_FILE
    config_file = os.environ.get(
        YAML_CONFIG_FILE_ENVIRONMENT_VARIABLE,
    )
    settings = yaml_load_settings_from_file(default_config_file)
    if config_file:
        custom_settings = yaml_load_settings_from_file(config_file)
        settings.update(custom_settings)
    return settings


def load_settings():
    method = os.environ.get(
        METHOD_ENVIRONMENT_VARIABLE,
        DEFAULT_METHOD
    )

    method_mappings = {
        "yaml": yaml_load_settings,
    }

    try:
        return method_mappings[method.lower()]()
    except KeyError as e:
        raise KeyError(
            "The {} environment variable is not set to a recognized "
            "method, but is rather set to {!r}. Recognized methods: "
            "{!r}"
            .format(
                METHOD_ENVIRONMENT_VARIABLE,
                method,
                list(method_mappings.keys())
            )
        ) from e
