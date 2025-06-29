def get_openai_response_format(required_response_keys: list[str]) -> dict:
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


def get_gemini_response_format(required_response_keys: list[str]) -> dict:
    keys_as_property_dict = convert_required_keys_to_property_dict(
        required_response_keys
    )
    return {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "object",
            "properties": keys_as_property_dict,
            "required": required_response_keys,
        },
    }


def get_anthropic_tool(required_response_keys: list[str]) -> list[dict]:
    keys_as_property_dict = convert_required_keys_to_property_dict(
        required_response_keys
    )
    return [
        {
            "name": "response",
            "description": "Response to the user's request using well-structured JSON.",
            "input_schema": {
                "type": "object",
                "properties": keys_as_property_dict,
                "required": required_response_keys,
            },
        }
    ]


def convert_required_keys_to_property_dict(required_respose_keys: list[str]) -> dict:
    ret = {}
    for key in required_respose_keys:
        ret[key] = {"type": "string"}
    return ret
