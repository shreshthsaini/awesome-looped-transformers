# Contributing to Awesome Looped Transformers

Thank you for helping keep this list complete and accurate! There are three ways to contribute.

## 1. Open an issue (easiest, fully automated)

| I want to... | Use |
|---|---|
| add a paper | [📝 Add a paper](../../issues/new?template=add-paper.yml) |
| add code, a checkpoint, blog, talk or benchmark | [🔗 Add a resource](../../issues/new?template=add-resource.yml) |
| fix a wrong date, venue, link or category | [🐛 Fix an entry](../../issues/new?template=fix-entry.yml) |

For **"Add a paper"**, paste the arXiv link, pick a category and write a one-sentence TL;DR. The bot then:

1. fetches the title, authors, first-submission date, venue hints and code link from the arXiv API,
2. checks the paper is not already listed (by arXiv id and by normalized title),
3. writes the entry to `data/papers.yaml`, regenerates `README.md` and the progress charts,
4. opens a pull request that closes your issue on merge, and comments back with what it found.

If something goes wrong (duplicate, broken link, unknown category) the bot explains on the issue and adds
the `needs-info` label. Edit the issue and it will retry.

## 2. Maintainer commands

Repository owners, members and collaborators can comment on **any** issue or PR:

```
/add-paper <arxiv-id-or-url> <category> [type] [code-url]
/add-paper 2502.05171 language-models Method https://github.com/seal-rg/recurrent-pretraining
```

Every Monday the **arXiv watch** workflow opens an issue listing new arXiv papers that mention looped /
recurrent-depth transformers, each with a ready-to-paste `/add-paper` line.

## 3. Edit the data by hand

`README.md` is **generated**. Never edit it directly; edit the YAML and the build bot does the rest.

```bash
pip install -r requirements.txt
# edit data/papers.yaml or data/resources.yaml
make build          # = validate + charts + README
```

### Paper fields (`data/papers.yaml`)

| Field | Required | Notes |
|---|:---:|---|
| `id` | ✅ | `firstauthorlastnameYEAR-three-title-words`, unique |
| `title` | ✅ | Exact title |
| `authors` | ✅ | List. If more than 6, list the first 5 and then `et al.` |
| `date` | ✅ | `YYYY-MM-DD`, the arXiv **v1** date (or publication date if not on arXiv) |
| `venue` | ✅ | e.g. `ICLR 2026`, `NeurIPS 2025 Workshop`, or `arXiv` if not (yet) accepted |
| `type` | ✅ | `Method`, `Theory`, `Analysis`, `Survey`, `Benchmark`, `Model` or `Position` |
| `category` | ✅ | One id from `data/config.yaml` (see below) |
| `tags` | | Topics from `data/config.yaml` (e.g. `language`, `diffusion`, `theory`) |
| `arxiv` | | arXiv id without version, e.g. `2502.05171` |
| `paper_url` | ✅ | Canonical link (arXiv abs page when available) |
| `code_url` | | **Official** implementation only |
| `project_url` | | Project page or released checkpoint |
| `stars` | | Filled in daily by the bot; do not edit |
| `tldr` | ✅ | One sentence, about 25 words, in your own words |
| `added` | | Date the entry was added (set by the bot) |

### Categories

| id | Covers |
|---|---|
| `surveys` | Surveys and position papers |
| `foundations` | Universal Transformers, cross-layer sharing, looped blocks as a design primitive |
| `theory` | Expressivity, Turing completeness, CoT equivalence, approximation, training dynamics |
| `in-context-learning` | Looped transformers implementing GD and other learners in context |
| `algorithmic-reasoning` | Arithmetic, graphs, puzzles, length and easy-to-hard generalization |
| `latent-reasoning` | HRM, TRM, latent thoughts, iterative refinement |
| `language-models` | Pretraining, scaling, test-time compute of looped LLMs |
| `adaptive-computation` | Halting, pondering, per-token recursion depth, early exit |
| `efficiency` | Recursive conversion of pretrained models, layer tying, KV sharing, fast inference |
| `diffusion-generative` | Looped / recurrent-depth backbones for diffusion and other generative models |
| `vision-multimodal` | Looped ViTs, multimodal, video, speech, robotics |
| `equilibrium-implicit` | Deep equilibrium and fixed-point transformers |
| `analysis-interpretability` | Probing, mechanistic studies, failure modes, comparisons |

## Inclusion criteria

A paper belongs here if **reusing the same weights across depth** (looping, recurrence in depth, weight
tying, recursion, or a fixed-point / equilibrium formulation) is **central** to its contribution. Papers
that merely mention looped models, or that use recurrence only over time/sequence (classic RNNs, SSMs), are
out of scope. When in doubt, open an issue and ask.

## Repository layout

```
data/config.yaml        categories, types, tags, plot groups, citation settings
data/papers.yaml        every paper (single source of truth)
data/resources.yaml     code, checkpoints, blogs, talks, benchmarks
templates/              README template
scripts/                build, validation, arXiv + GitHub helpers, bots
assets/                 logo and generated charts
.github/workflows/      add-entry bot, README build, validation, star refresh, arXiv watch, link check
```

## One-time setup for forks / maintainers

The bots need **Settings → Actions → General → Workflow permissions → "Read and write permissions"** and
**"Allow GitHub Actions to create and approve pull requests"** enabled. Labels are created automatically on
the first build.
