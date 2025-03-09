def get_response_format(required_response_keys: list[str]) -> dict:
    keys_as_property_dict = convert_required_keys_to_property_dict(
        required_response_keys
    )
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "response",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": keys_as_property_dict,
                "required": required_response_keys,
                "additionalProperties": False,
            },
        },
    }


def convert_required_keys_to_property_dict(required_respose_keys: list[str]) -> dict:
    ret = {}
    for key in required_respose_keys:
        ret[key] = {"type": "string"}
    return ret
