"""
Cryptopia SDK

Usage in notebooks:
    import cryptopia as cx

    value = cx.slider("Alpha", min=0.0, max=1.0, value=0.5, step=0.01)
    selected = cx.select("Method", ["SGD", "Adam", "RMSProp"])
    cx.chart({
        "xAxis": {"data": [1, 2, 3]},
        "yAxis": {},
        "series": [{"type": "line", "data": [value, value*2, value*3]}]
    })
"""

from cryptopia.widgets import (
    slider,
    select,
    text_input,
    button,
    checkbox,
    chart,
    dataframe,
    text,
    latex,
    _dispatch,  # called by the backend's /dispatch endpoint
)

__version__ = "0.1.0"
__all__ = [
    "slider",
    "select",
    "text_input",
    "button",
    "checkbox",
    "chart",
    "dataframe",
    "text",
    "latex",
]
