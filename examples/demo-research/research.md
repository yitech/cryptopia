---
title: Gradient Descent Visualisation
description: An interactive exploration of gradient descent driven by SDK on_change callbacks — the page renders charts, sliders mutate state, and only the affected cell re-emits.
tags: [optimisation, machine-learning, interactive]
interactive: true
---

# Gradient Descent Visualisation

An interactive exploration of stochastic gradient descent on the quadratic
loss $L(x) = (x + 1)^2$. Adjust the controls in the sidebar — every move
calls a single Python function in the kernel that recomputes the trajectory
and re-emits the affected charts.

The update rule for SGD with momentum is:

$$
v_{t+1} = \mu v_t - \alpha \nabla L(\theta_t)
$$

$$
\theta_{t+1} = \theta_t + v_{t+1}
$$

where $\alpha$ is the **learning rate** and $\mu$ is the **momentum
coefficient**. Adam additionally maintains exponential averages $m_t$ and
$s_t$ of the gradient and its square.

## How this page reacts

The page registers an `on_change` callback for each input widget. When you
move a slider, the frontend posts the new value to `/api/pages/.../dispatch`
and the kernel runs the callback — no full page re-execution.

For reference, this is the SGD step the page implements:

```python
# Display-only — the live version is in the #core cell below.
def sgd_step(x, lr):
    return x - lr * grad(x)
```

## The optimiser

```python {.run #core}
import math


def loss(x: float) -> float:
    return x ** 2 + 2 * x + 1


def grad(x: float) -> float:
    return 2 * x + 2


def optimise(lr: float, momentum: float, n_steps: int, optimizer: str):
    """Run `n_steps` of the chosen optimiser starting from x=3.0.

    Returns (trajectory, losses) — both lists of length n_steps + 1.
    """
    x = 3.0
    trajectory = [x]
    losses = [loss(x)]

    v = 0.0
    m = 0.0
    s = 0.0
    beta1, beta2, eps = 0.9, 0.999, 1e-8

    for t in range(1, int(n_steps) + 1):
        g = grad(x)
        if optimizer == 'SGD':
            x = x - lr * g
        elif optimizer == 'SGD + Momentum':
            v = momentum * v - lr * g
            x = x + v
        else:  # Adam
            m = beta1 * m + (1 - beta1) * g
            s = beta2 * s + (1 - beta2) * g ** 2
            m_hat = m / (1 - beta1 ** t)
            s_hat = s / (1 - beta2 ** t)
            x = x - lr * m_hat / (math.sqrt(s_hat) + eps)
        trajectory.append(x)
        losses.append(loss(x))

    return trajectory, losses
```

## Controls and live charts

```python {.run #render}
import cryptopia as cx
import pandas as pd

# Single source of truth for the current widget values. Each on_change
# handler mutates one field and triggers a re-render — that's the entire
# reactivity contract.
state = {
    'lr': 0.05,
    'momentum': 0.9,
    'n_steps': 50,
    'optimizer': 'SGD + Momentum',
}


def render() -> None:
    """Recompute the optimisation and emit charts/table.

    Charts use stable `key=` arguments so dispatch can replace them in-place
    rather than appending a new copy on every slider move.
    """
    trajectory, losses = optimise(
        state['lr'], state['momentum'], state['n_steps'], state['optimizer']
    )
    steps = list(range(len(losses)))

    cx.chart(
        {
            'title': {'text': f'Loss curve — {state["optimizer"]}',
                      'textStyle': {'color': '#e2e8f0'}},
            'backgroundColor': 'transparent',
            'xAxis': {'type': 'category', 'data': steps, 'name': 'Step'},
            'yAxis': {'type': 'value', 'name': 'Loss'},
            'series': [{
                'name': 'Loss',
                'type': 'line',
                'data': [round(L, 6) for L in losses],
                'smooth': True,
                'lineStyle': {'width': 2},
                'areaStyle': {'opacity': 0.1},
            }],
            'tooltip': {'trigger': 'axis'},
        },
        height=320,
        key='loss-chart',
    )

    xs = [round(x, 4) for x in trajectory]
    ys = [round(loss(x), 6) for x in trajectory]
    cx.chart(
        {
            'title': {'text': 'Trajectory in parameter space',
                      'textStyle': {'color': '#e2e8f0'}},
            'backgroundColor': 'transparent',
            'xAxis': {'type': 'value', 'name': 'x', 'min': -2, 'max': 4},
            'yAxis': {'type': 'value', 'name': 'L(x)'},
            'series': [
                {
                    'name': 'Loss surface',
                    'type': 'line',
                    'data': [[round(-2 + i * 0.1, 1), round(loss(-2 + i * 0.1), 4)]
                             for i in range(61)],
                    'lineStyle': {'color': '#334155', 'width': 1},
                    'showSymbol': False,
                },
                {
                    'name': 'Trajectory',
                    'type': 'line',
                    'data': list(zip(xs, ys)),
                    'lineStyle': {'color': '#0ea5e9', 'width': 2},
                    'itemStyle': {'color': '#0ea5e9'},
                    'symbolSize': 4,
                },
            ],
            'tooltip': {'trigger': 'axis'},
        },
        height=320,
        key='trajectory-chart',
    )

    every = max(1, len(steps) // 10)
    summary = pd.DataFrame({
        'Step': steps[::every],
        'x': [round(trajectory[i], 6) for i in steps[::every]],
        'Loss': [round(losses[i], 8) for i in steps[::every]],
    })
    cx.dataframe(summary, title='Optimisation progress', key='summary-table')


def _update(name, cast):
    def handler(value):
        state[name] = cast(value)
        render()
    return handler


# Register the widgets and their callbacks. The kernel keeps both the
# `state` dict and the `render` closure alive across HTTP requests, so a
# slider move only needs to invoke one handler.
state['lr'] = cx.slider(
    'Learning rate (α)', min=0.001, max=0.5, value=state['lr'], step=0.001,
    on_change=_update('lr', float),
)
state['momentum'] = cx.slider(
    'Momentum (μ)', min=0.0, max=0.99, value=state['momentum'], step=0.01,
    on_change=_update('momentum', float),
)
state['n_steps'] = cx.slider(
    'Steps', min=10, max=200, value=state['n_steps'], step=10, key='n_steps',
    on_change=_update('n_steps', int),
)
state['optimizer'] = cx.select(
    'Optimiser', ['SGD', 'SGD + Momentum', 'Adam'], value=state['optimizer'],
    on_change=_update('optimizer', str),
)

render()
```

## Key observations

- **High learning rate**: faster initial descent but may oscillate near the
  minimum, occasionally overshooting on the trajectory chart.
- **Momentum**: smooths the descent and helps the trajectory accelerate
  through shallow regions of the loss surface.
- **Adam**: adaptive per-parameter learning rates; converges quickly even
  when the base learning rate is set very low.

The theoretical convergence rate for SGD on $\mu$-strongly convex functions
is:

$$
\mathbb{E}[L(\theta_T) - L^*] \leq (1 - \alpha\mu)^T (L(\theta_0) - L^*)
$$

so each slider move on this page is, in essence, sampling one point on that
exponential decay curve.
