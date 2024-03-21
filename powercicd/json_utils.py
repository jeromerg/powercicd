import logging
from jsonpath_ng.ext import parse

log = logging.getLogger(__name__)


def apply_substitution(json_tree, value_path, replacement):
    log.info(f"Applying substitution '{value_path}' -> '{replacement}':")
    parser = parse(value_path)        
    count = 0
    for match in parser.find(json_tree):
        count += 1
        full_path = match.full_path
        value = match.value
        log.info(f"- Replacing at '{full_path}' old value '{value}' with '{replacement}'")
        value.update(json_tree, replacement)
    if count == 0:
        log.info(f"- Substitution '{value_path}' -> '{replacement}' did not match any value.")
