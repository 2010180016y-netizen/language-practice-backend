"""Generate simple Retrofit interface + data models from openapi.json.

Usage:
    python scripts/android/generate_retrofit_from_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / 'openapi.json'
OUT_DIR = ROOT / 'android'


def to_pascal(name: str) -> str:
    parts = [p for p in name.replace('-', '_').replace('.', '_').split('_') if p]
    return ''.join(p[:1].upper() + p[1:] for p in parts) or 'Model'


def kotlin_type(schema: dict) -> str:
    t = schema.get('type')
    if '$ref' in schema:
        return schema['$ref'].split('/')[-1]
    if t == 'string':
        return 'String'
    if t == 'integer':
        return 'Int'
    if t == 'number':
        return 'Double'
    if t == 'boolean':
        return 'Boolean'
    if t == 'array':
        return f"List<{kotlin_type(schema.get('items', {}))}>"
    if t == 'object':
        return 'Map<String, Any>'
    return 'Any'


def generate_models(spec: dict) -> str:
    schemas = spec.get('components', {}).get('schemas', {})
    lines = [
        'package com.languageapp.api',
        '',
        'import kotlinx.serialization.Serializable',
        '',
    ]

    for name, sch in schemas.items():
        if sch.get('type') != 'object':
            continue
        required = set(sch.get('required', []))
        props = sch.get('properties', {})
        lines.append('@Serializable')
        lines.append(f'data class {name}(')
        fields = []
        for prop_name, prop_schema in props.items():
            kt = kotlin_type(prop_schema)
            nullable = '' if prop_name in required else '? = null'
            fields.append(f'    val {prop_name}: {kt}{nullable}')
        lines.append(',\n'.join(fields) if fields else '    val _placeholder: String? = null')
        lines.append(')')
        lines.append('')
    return '\n'.join(lines)


def _build_method_params(path: str, op: dict) -> tuple[list[str], list[str], list[str]]:
    imports: list[str] = []
    annotations: list[str] = []
    params: list[str] = []

    for p in op.get('parameters', []):
        name = p['name']
        schema = p.get('schema', {'type': 'string'})
        kt = kotlin_type(schema)
        if p.get('in') == 'path':
            imports.append('import retrofit2.http.Path')
            annotations.append(f'@Path("{name}") {name}: {kt}')
        elif p.get('in') == 'query':
            imports.append('import retrofit2.http.Query')
            annotations.append(f'@Query("{name}") {name}: {kt}? = null')

    body = op.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema')
    if body:
        imports.append('import retrofit2.http.Body')
        annotations.append(f'@Body body: {kotlin_type(body)}')

    params.extend(annotations)
    return imports, params, []


def generate_api(spec: dict) -> str:
    imports = {'import retrofit2.http.*'}
    methods = []

    for path, item in sorted(spec.get('paths', {}).items()):
        effective_path = f"/v1{path}" if not path.startswith('/v1') else path
        for method in ('get', 'post', 'put', 'delete', 'patch'):
            op = item.get(method)
            if not op:
                continue
            op_id = to_pascal(op.get('operationId') or f"{method}_{path.strip('/').replace('/', '_')}")

            imp, params, _ = _build_method_params(path, op)
            for i in imp:
                imports.add(i)

            # choose best success code
            responses = op.get('responses', {})
            schema = None
            for code in ('200', '201', '202', '204'):
                schema = responses.get(code, {}).get('content', {}).get('application/json', {}).get('schema')
                if schema is not None:
                    break
            ret = kotlin_type(schema) if schema else 'Unit'

            methods.append(f'    @{method.upper()}("{effective_path}")')
            methods.append(f'    suspend fun {op_id}({", ".join(params)}): {ret}')
            methods.append('')

    lines = [
        'package com.languageapp.api',
        '',
        *sorted(imports),
        '',
        'interface LanguageApiV1 {',
        *methods,
        '}',
    ]
    return '\n'.join(lines)


def main() -> None:
    if not OPENAPI.exists():
        raise SystemExit('openapi.json not found. Run: python scripts/export_openapi.py')

    spec = json.loads(OPENAPI.read_text(encoding='utf-8'))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / 'ApiModels.kt').write_text(generate_models(spec), encoding='utf-8')
    (OUT_DIR / 'LanguageApiV1.kt').write_text(generate_api(spec), encoding='utf-8')

    print('generated android/ApiModels.kt and android/LanguageApiV1.kt')


if __name__ == '__main__':
    main()
