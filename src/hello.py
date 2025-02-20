import sys

import matplotlib.pyplot as plt
import numpy as np


def create_figure(path: str):
    # Create sample data
    x = np.linspace(0, 10, 100)
    y = np.sin(x)

    # Create the figure
    plt.figure(figsize=(8, 6))
    plt.plot(x, y, "b-", label="sin(x)")
    plt.title("Example Sine Wave")
    plt.xlabel("x")
    plt.ylabel("sin(x)")
    plt.grid(True)
    plt.legend()

    # Save the figure
    plt.savefig(path)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 hello.py <output-path>")
        sys.exit(1)

    create_figure(sys.argv[1])


if __name__ == "__main__":
    main()
