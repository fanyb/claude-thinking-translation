# Included software and model

- Claude Thinking Translation is MIT-licensed. See `LICENSE`.
- CPython is distributed under the [Python Software Foundation license](https://docs.python.org/3/license.html). The redistribution uses [Python Build Standalone](https://github.com/astral-sh/python-build-standalone), whose bundle includes component licenses.
- CTranslate2, SentencePiece and NumPy are redistributed with the licenses in their respective `.dist-info` directories.
- English-to-Chinese translation uses the [Argos model 1.9](https://github.com/argosopentech/argospm-index) derived from [OPUS-MT](https://aclanthology.org/2020.eamt-1.61/) by Jörg Tiedemann and Santhosh Thottingal. It is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This installer extracts the inference files from the original archive. It does not retrain or modify the model.
