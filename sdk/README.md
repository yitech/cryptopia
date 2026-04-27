# Cryptopia SDK

Interactive widget primitives for Cryptopia research notebooks.

## Installation

```bash
pip install cryptopia
```

Or from the monorepo:

```bash
pip install -e /path/to/cryptopia/sdk
```

## Usage

```python
import cryptopia as cx

# Slider — returns current float value
alpha = cx.slider("Learning rate", min=0.0001, max=0.1, value=0.01, step=0.0001)

# Dropdown select
optimizer = cx.select("Optimizer", ["SGD", "Adam", "RMSProp"], value="Adam")

# Text input
label = cx.text_input("Dataset label", value="train")

# Button — returns True when clicked
if cx.button("Run training"):
    print("Training...")

# Checkbox
normalize = cx.checkbox("Normalize inputs", value=True)

# ECharts chart
cx.chart({
    "title": {"text": "Loss curve"},
    "xAxis": {"type": "category", "data": list(range(100))},
    "yAxis": {"type": "value"},
    "series": [{"type": "line", "data": [1/(i+1)*alpha for i in range(100)]}],
})

# Pandas DataFrame table
import pandas as pd
cx.dataframe(pd.DataFrame({"x": [1,2,3], "y": [4,5,6]}), title="Sample data")

# Rich text / LaTeX
cx.text("## Results\n\nThe following formula governs the process:")
cx.latex(r"\mathcal{L}(\theta) = -\sum_{i} y_i \log \hat{y}_i")
```

## Reactivity with `on_change`

Input widgets accept an `on_change=` callable. When the user moves a slider or
picks a select option in a published Cryptopia page, the frontend POSTs
`/dispatch` and the kernel invokes the callback with the new value. The
callback can call other `cx.*` primitives, and any widgets / charts it emits
are streamed back as the response — without re-running the whole cell.

```python
import cryptopia as cx

def update(v):
    cx.chart({
        "title": {"text": f"alpha = {v:.3f}"},
        "xAxis": {"data": list(range(50))},
        "yAxis": {},
        "series": [{"type": "line", "data": [v * i for i in range(50)]}],
    }, key="alpha-chart")

alpha = cx.slider("alpha", min=0.0, max=1.0, value=0.1, on_change=update)
update(alpha)
```

A widget without `on_change` is purely cosmetic until the cell that owns it
is re-run — useful for displaying values that other cells consume.

## Fallback behaviour

When running locally in Jupyter (outside Cryptopia), all `cx.*` calls return their
`value` / default parameter without emitting widgets, so notebooks work normally.
`on_change` callbacks are stored against `__main__.__cx_callbacks__` and remain
inert unless `cryptopia._dispatch(widget_id, value)` is invoked.
