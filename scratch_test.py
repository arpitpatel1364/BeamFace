import numpy as np

def old_apply(signal: np.ndarray, delay_samples: float) -> np.ndarray:
    n = len(signal)
    signal = signal.astype(np.float32)

    if delay_samples == 0.0:
        return signal.copy()

    delay_int = int(np.floor(delay_samples))
    frac = delay_samples - delay_int

    if delay_int > 0:
        pad1 = np.zeros(delay_int, dtype=np.float32)
        delayed_1 = np.concatenate([pad1, signal])[:n]
        pad2 = np.zeros(delay_int + 1, dtype=np.float32)
        delayed_2 = np.concatenate([pad2, signal])[:n]
    elif delay_int == 0:
        delayed_1 = signal.copy()
        pad2 = np.zeros(1, dtype=np.float32)
        delayed_2 = np.concatenate([pad2, signal])[:n]
    else:
        advance = -delay_int
        pad1 = np.zeros(advance, dtype=np.float32)
        delayed_1 = np.concatenate([signal[advance:], pad1])[:n]
        if advance > 1:
            pad2 = np.zeros(advance - 1, dtype=np.float32)
            delayed_2 = np.concatenate([signal[advance - 1:], pad2])[:n]
        else:
            delayed_2 = signal.copy()

    return (1.0 - frac) * delayed_1 + frac * delayed_2


def new_apply(signal: np.ndarray, delay_samples: float) -> np.ndarray:
    n = len(signal)
    signal = signal.astype(np.float32)

    if delay_samples == 0.0:
        return signal.copy()

    delay_int = int(np.floor(delay_samples))
    frac = delay_samples - delay_int

    def shift_array(arr: np.ndarray, shift: int) -> np.ndarray:
        res = np.zeros_like(arr)
        if shift > 0:
            if shift < n:
                res[shift:] = arr[:-shift]
        elif shift < 0:
            if -shift < n:
                res[:shift] = arr[-shift:]
        else:
            res[:] = arr
        return res

    delayed_1 = shift_array(signal, delay_int)
    delayed_2 = shift_array(signal, delay_int + 1)

    return (1.0 - frac) * delayed_1 + frac * delayed_2

sig = np.arange(10, dtype=np.float32)
for d in [0.0, 1.2, -1.2, 2.5, -2.5, 0.5, -0.5]:
    o = old_apply(sig, d)
    n = new_apply(sig, d)
    assert np.allclose(o, n), f"Failed for {d}:\n{o}\n{n}"
print("All matched!")
