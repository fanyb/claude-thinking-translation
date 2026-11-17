"""Translate one JSON string per line using a locally installed Argos model."""
import json
from pathlib import Path
import sys

import ctranslate2
import sentencepiece


model = Path(__file__).resolve().parent / 'model'
tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(model / 'sentencepiece.model'))
translator = ctranslate2.Translator(str(model / 'model'), device='cpu', inter_threads=1, intra_threads=2)
for line in sys.stdin:
    text = json.loads(line)
    result = translator.translate_batch([tokenizer.encode(text, out_type=str)], beam_size=4,
                                        replace_unknowns=True, max_decoding_length=360)[0]
    translated = tokenizer.decode(result.hypotheses[0]).replace('▁', ' ').strip()
    print(json.dumps(translated), flush=True)
