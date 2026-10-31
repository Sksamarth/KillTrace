"""Bounded raw-file to JSONL conversion; preserves values, never guesses types."""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path


TOKEN = re.compile(r'([^\s=]+)=("(?:\\.|[^"\\])*"|[^\s"]*)')


def parse_key_values(message):
    fields, position = {}, 0
    while position < len(message):
        while position < len(message) and message[position].isspace():
            position += 1
        if position == len(message):
            break
        match = TOKEN.match(message, position)
        if match is None:
            raise ValueError("invalid key=value framing")
        key, value = match.groups()
        if key in fields:
            raise ValueError("duplicate key")
        if value.startswith('"'):
            # Only decode quote/backslash escapes; preserve other literal escapes.
            value = re.sub(r'\\(["\\])', r'\1', value[1:-1])
        fields[key] = value
        position = match.end()
        if position < len(message) and not message[position].isspace():
            raise ValueError("missing field separator")
    if not fields or message[position:].strip():
        raise ValueError("not a complete key=value record")
    return fields


def convert(source, output, profile="key-value", cancel_file=None):
    from app.ingestion import records
    if profile not in {'key-value', 'text', 'jsonl'}:
        raise ValueError("unsupported conversion profile")
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.exists() or output.with_suffix(output.suffix+'.manifest.json').exists():
        raise FileExistsError("refusing to overwrite source/output")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix+'.partial')
    before = source.stat()
    count = rejected = 0
    with source.open('rb') as stream, partial.open('xb', buffering=1024**2) as sink:
        for number, offset, length, raw_hash, raw in records(stream):
            if cancel_file and Path(cancel_file).exists():
                raise InterruptedError("conversion cancelled; partial output retained, final output not published")
            record = {"record_number": number, "byte_offset": offset, "byte_length": length, "raw_sha256": raw_hash}
            if raw is None:
                record['issues']=['record_too_large']
                rejected += 1
            else:
                try:
                    message = raw.decode('utf-8').removesuffix('\n').removesuffix('\r')
                    if profile == 'key-value':
                        record['fields'] = parse_key_values(message)
                    elif profile == 'jsonl':
                        from app.contracts.v1 import unique_object, reject_constant
                        record['fields'] = json.loads(message, object_pairs_hook=unique_object, parse_constant=reject_constant)
                        if not isinstance(record['fields'], dict):
                            raise ValueError("JSON Lines record must be an object")
                    else:
                        record['message'] = message
                    # JSON numbers such as 1e999 overflow Python floats; do not
                    # let one malformed record abort an otherwise valid file.
                    encoded = json.dumps(record,ensure_ascii=True,separators=(',',':'),allow_nan=False)
                except (UnicodeDecodeError, ValueError, RecursionError):
                    record.pop('fields', None)
                    record['issues']=['invalid_encoding_or_record']
                    rejected += 1
                    # Original bytes remain addressable even if decoding failed.
                    record['message'] = raw.decode('utf-8', errors='replace').removesuffix('\n')
                else:
                    sink.write((encoded+'\n').encode())
            if raw is None or 'issues' in record:
                sink.write((json.dumps(record,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode())
            count = number
            if number % 100000 == 0:
                sink.flush()
                if shutil.disk_usage(output.parent).free < 256*1024**2:
                    raise OSError("free disk reserve exhausted; partial output retained")
                print(f'{number:,} records / {offset+length:,} source bytes',flush=True)
        sink.flush()
        os.fsync(sink.fileno())
    # Full hash includes oversized records without accumulating them in memory.
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        while block := stream.read(1024**2):
            digest.update(block)
    if source.stat().st_size != before.st_size or source.stat().st_mtime_ns != before.st_mtime_ns:
        raise ValueError("source changed during conversion")
    manifest = {"version":"1.0.0","source":str(source),"source_bytes":before.st_size,"source_sha256":digest.hexdigest(),"profile":profile,"records":count,"records_with_issues":rejected,"output_bytes":partial.stat().st_size,"limitations":"UTF-8 physical lines; no semantic field inference, multiline reconstruction or binary decoding"}
    partial.rename(output)
    with output.with_suffix(output.suffix+'.manifest.json').open('x',encoding='utf-8') as stream:
        json.dump(manifest,stream,indent=2)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--profile',choices=['key-value','text','jsonl'],default='key-value')
    parser.add_argument('--cancel-file',type=Path)
    args=parser.parse_args()
    print(json.dumps(convert(args.source,args.output,args.profile,args.cancel_file),indent=2))
