# Binary Ninja Advanced Search

**Advanced Search** is a Python UI plugin for Binary Ninja that finds functions associated with behavior categories such as purchase workflows, credential access, networking, persistence, and anti-analysis. It has a deterministic local mode that requires no network access and an optional AI mode that works with OpenAI-compatible providers.

## Features

| Capability | Description |
|---|---|
| Category search | Searches function names, string evidence, disassembly text, and common indicators. |
| Categories | Purchase / commerce, credential access, networking, file activity, process execution, persistence, surveillance / collection, cryptography / crypto-mining, and anti-analysis. |
| Free-form query | Narrows local results to functions whose collected evidence contains the query text. |
| AI-assisted search | Sends a bounded summary of function names, addresses, and evidence to `POST /chat/completions`. |
| Provider choice | Supports OpenAI, Azure-compatible gateways, local servers, and other providers exposing the OpenAI chat-completions contract. |
| Settings | All AI options are under Binary Ninja Settings → Advanced Search. |
| Navigation | Double-click any result to navigate to the function address. |

## Installation

Copy the `bn_feature_search` directory and `plugin.json` into a Binary Ninja plugin directory. The exact directory is available from **Binary Ninja → Settings → Plugins → Open Plugin Folder**. Restart Binary Ninja, or reload the module from the Python console during development.

For a local checkout, the plugin directory is the repository root:

```text
advanced-search/
├── plugin.json
├── README.md
└── bn_feature_search/
    ├── __init__.py
    ├── ai.py
    └── search.py
```

## Usage

Open a binary and choose **Plugins → Advanced Search → Search…**. Select one or more categories, optionally enter a free-form query, and press **Search**. The default selection emphasizes purchase, networking, and credential-access indicators; clear or change the selection for a different investigation.

Choose **AI-assisted search** only after configuring a provider. AI mode is intended for semantic matching over the local evidence summary; it does not automatically decompile the whole binary or modify analysis metadata. Results are restricted to functions present in the summary, which prevents the model from creating arbitrary addresses.

## Configuration

The plugin registers these settings:

| Setting | Default | Purpose |
|---|---:|---|
| `AdvancedSearch.ai.enabled` | `false` | Explicit opt-in for networked AI search. |
| `AdvancedSearch.ai.base_url` | `https://api.openai.com/v1` | Provider root URL; `/chat/completions` is appended. |
| `AdvancedSearch.ai.api_key` | empty | Provider credential. |
| `AdvancedSearch.ai.model` | `gpt-4o-mini` | Provider-specific model identifier. |
| `AdvancedSearch.ai.timeout_seconds` | `30` | Network timeout, clamped to a safe range. |
| `AdvancedSearch.ai.max_functions` | `250` | Maximum function summaries included in one request. |

The plugin does not ship an API key, does not log requests, and does not transmit anything in local mode. Before enabling AI mode, confirm that the selected provider is acceptable for the binary and strings under analysis.

## Compatible provider example

A provider rooted at `http://127.0.0.1:1234/v1` with model `local-model` can be configured entirely through Binary Ninja Settings. The provider must accept JSON requests with `model`, `messages`, `temperature`, and `response_format`, and return the usual `choices[0].message.content` JSON object containing a `matches` array.

## Development

The implementation intentionally uses only the Python standard library for HTTP requests. Binary Ninja itself supplies the `binaryninja` and `binaryninjaui` modules. For headless checks outside Binary Ninja, compile the source files with:

```bash
python3 -m py_compile bn_feature_search/search.py bn_feature_search/ai.py bn_feature_search/__init__.py
```

For hot reload during plugin development, use the Binary Ninja Python console:

```python
import importlib
import bn_feature_search
importlib.reload(bn_feature_search)
```

## Limitations

Local evidence quality depends on the analysis state and available function metadata. The plugin is a triage aid rather than a malware verdict. AI output is advisory and should be validated against the disassembly and the underlying binary.

## References

[1]: https://docs.binary.ninja/dev/plugins.html "Binary Ninja User Documentation: Writing Plugins"

[2]: https://platform.openai.com/docs/api-reference/chat "OpenAI API Reference: Chat Completions"
