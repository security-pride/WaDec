# WaDec

WaDec is an approach leveraging a fine-tuned LLM to decompile Wasm binary code into a more comprehensible source code. The model's training on a specialized **wat-c** dataset, coupled with self-supervised learning, has proven pivotal in enhancing decompilation efficacy. Our results indicate that WaDec significantly outperforms existing tools, achieving a minimal code inflation rate and maintaining high recompilability and re-execution rates. This advancement not only bolsters the readability and analyzability of Wasm code but also paves the way for more robust automated code analysis, optimization, and security auditing processes.

## Dataset

Our dataset is specifically designed for decompiling WebAssembly (Wasm). It includes100k+ pairs of WebAssembly Text (Wat) snippets and C code snippets at the loop level, providing a finer granularity than function-level datasets. The features of the dataset are as follows:

- **Wat snippet**: Segmented based on loop blocks.
- **C snippet**: Segmented based on loop blocks, corresponding to wat snippet.
- **Spatial info**: Function declarations for called functions.
- **Temporal info**: Local variables already defined before current snippet.
- **Offset2string**: Mapping from offsets to string constants.

## Getting Started

### Prerequisites

Ensure you have the following prerequisites installed:

- [Python 3.x](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)

### Installation

Clone the repository to your local machine:

```bash
git clone https://anonymous.4open.science/r/WaDec-EDDE
cd WaDec-EDDE
```

