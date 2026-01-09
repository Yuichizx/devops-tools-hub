# /app/utils/linter_service.py

from yamllint import linter
from yamllint.config import YamlLintConfig
from ruamel.yaml import YAML
import tempfile
import os
import io
import logging

# Siapkan logger untuk file ini jika diperlukan
logger = logging.getLogger(__name__)

def run_yaml_linting(content: str) -> dict:
    """
    Menjalankan validasi dan linting pada konten YAML dalam dua tahap.
    
    Returns:
        dict: Berisi 'status' dan data pendukungnya.
    """
    if not content:
        return {"status": "INVALID_SYNTAX", "error_message": "Konten tidak boleh kosong."}

    # Tahap 1: Validasi Sintaksis dengan ruamel.yaml
    yaml_parser = YAML()
    try:
        yaml_parser.load(content)
    except Exception as e:
        logger.warning(f"Invalid YAML syntax: {e}")
        return {"status": "INVALID_SYNTAX", "error_message": f"Kesalahan sintaksis YAML: {str(e)}"}

    # Tahap 2: Validasi Kualitas (Linting) dengan yamllint
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml', encoding='utf-8') as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        conf = YamlLintConfig('extends: default')
        with open(tmp_path, 'r', encoding='utf-8') as tmp_file:
            problems = list(linter.run(tmp_file, conf, tmp_path))
        
        results = [{'line': p.line, 'col': p.column, 'level': p.level, 'message': p.desc} for p in problems]

        if not results:
            return {"status": "PERFECT", "problems": []}
        else:
            return {"status": "VALID_WITH_ISSUES", "problems": results}

    except Exception as e:
        logger.exception("Error during yamllint process")
        raise e
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# [FUNGSI YANG PERLU DITAMBAHKAN]
def auto_fix_yaml(content: str) -> str:
    """
    Mencoba memperbaiki masalah umum pada konten YAML.
    - Menambahkan '---' jika tidak ada.
    - Memperbaiki indentasi dan format dasar.
    
    Args:
        content (str): String berisi teks YAML yang akan diperbaiki.

    Returns:
        str: Konten YAML yang sudah diformat dan diperbaiki.
    """
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.preserve_quotes = True
    
    if not content.strip().startswith('---'):
        content = '---\n' + content

    try:
        data = yaml.load(content)
        string_stream = io.StringIO()
        yaml.dump(data, string_stream)
        fixed_content = string_stream.getvalue()
        return fixed_content
    except Exception:
        # Jika gagal memperbaiki, kembalikan konten asli
        logger.warning("Could not auto-fix YAML, returning original content.")
        return content
