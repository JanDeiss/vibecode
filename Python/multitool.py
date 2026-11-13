#!/usr/bin/env python3
"""PocketKit: a dependency-free terminal toolbox for Python 3.10+."""

from __future__ import annotations

import ast
import hashlib
import math
import operator
import os
from pathlib import Path
import secrets
import string
import sys
import time


def enable_color() -> bool:
    if not sys.stdout.isatty() or "NO_COLOR" in os.environ:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel = ctypes.windll.kernel32
            handle = kernel.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            return bool(kernel.SetConsoleMode(handle, mode.value | 0x0004))
        except (AttributeError, OSError):
            return False
    return True


COLOR = enable_color()


def paint(text: str, code: str = "96") -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def heading(title: str) -> None:
    print(paint(f"\n  +{'-' * 54}+"))
    print(paint(f"  | {title:<52} |"))
    print(paint(f"  +{'-' * 54}+"))


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or (default if default is not None else "")


def integer(prompt: str, default: int, minimum: int, maximum: int) -> int:
    while True:
        try:
            value = int(ask(prompt, str(default)))
            if minimum <= value <= maximum:
                return value
        except ValueError:
            pass
        print(paint(f"  Enter a whole number from {minimum} to {maximum}.", "93"))


def number(prompt: str) -> float:
    while True:
        try:
            value = float(ask(prompt))
            if math.isfinite(value):
                return value
        except ValueError:
            pass
        print(paint("  Enter a finite number.", "93"))


def yes(prompt: str, default: bool = True) -> bool:
    while True:
        answer = ask(prompt + " (y/n)", "y" if default else "n").lower()
        if answer in {"y", "yes", "n", "no"}:
            return answer in {"y", "yes"}
        print("  Please enter y or n.")


OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
FUNCTIONS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "abs": abs, "round": round,
    "floor": math.floor, "ceil": math.ceil,
}


def calculate(expression: str, answer: float = 0) -> int | float:
    """Evaluate a small, bounded math grammar; never execute Python code."""
    if not expression.strip() or len(expression) > 256:
        raise ValueError("Use an expression between 1 and 256 characters.")
    try:
        tree = ast.parse(expression, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > 80:
            raise ValueError("That expression is too complex.")

        def bounded(value: object) -> int | float:
            if type(value) not in (int, float):
                raise ValueError("Only real numbers are supported.")
            if not math.isfinite(value) or abs(value) > 1e100:
                raise ValueError("Result is too large (limit: 1e100).")
            return value

        def visit(node: ast.AST) -> int | float:
            if isinstance(node, ast.Constant):
                return bounded(node.value)
            if isinstance(node, ast.Name):
                constants = {"pi": math.pi, "e": math.e, "tau": math.tau, "ans": answer}
                if node.id in constants:
                    return bounded(constants[node.id])
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = visit(node.operand)
                return bounded(-value if isinstance(node.op, ast.USub) else value)
            if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 100:
                    raise ValueError("Exponents must be between -100 and 100.")
                return bounded(OPERATORS[type(node.op)](left, right))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FUNCTIONS and not node.keywords and len(node.args) <= 2:
                    return bounded(FUNCTIONS[node.func.id](*(visit(arg) for arg in node.args)))
            raise ValueError("Unsupported expression. Use numbers, math operators, and listed functions.")

        return visit(tree.body)
    except (SyntaxError, TypeError, OverflowError, ZeroDivisionError, RecursionError) as exc:
        raise ValueError("Invalid math, wrong function arguments, or result outside the supported range.") from exc


def calculator() -> None:
    heading("CALCULATOR")
    print("  Operators: + - * / // % ** and parentheses")
    print("  Functions: " + ", ".join(FUNCTIONS))
    print("  Constants: pi, e, tau, ans | Angles use radians.")
    print("  Example: sqrt(144) + 2**3 | Type 'back' to leave.")
    answer: int | float = 0
    while True:
        expression = ask("math")
        if expression.lower() in {"back", "q", "quit"}:
            return
        try:
            answer = calculate(expression, answer)
            print(paint(f"  = {answer:.12g}", "92"))
        except ValueError as exc:
            print(paint(f"  {exc}", "93"))


UNITS = {
    "length": {"mm": .001, "cm": .01, "m": 1, "km": 1000,
               "in": .0254, "ft": .3048, "yd": .9144, "mi": 1609.344},
    "mass": {"mg": .000001, "g": .001, "kg": 1, "oz": .028349523125, "lb": .45359237},
    "time": {"s": 1, "min": 60, "h": 3600, "day": 86400, "week": 604800},
    "data": {"b": 1, "kb": 1000, "mb": 1e6, "gb": 1e9,
             "kib": 1024, "mib": 1024**2, "gib": 1024**3},
}


def convert(value: float, category: str, source: str, target: str) -> float:
    if not math.isfinite(value):
        raise ValueError("Enter a finite value.")
    source, target = source.lower(), target.lower()
    if category == "temperature":
        if source not in {"c", "f", "k"} or target not in {"c", "f", "k"}:
            raise ValueError("Choose C, F, or K.")
        celsius = (value - 32) * 5 / 9 if source == "f" else value - 273.15 if source == "k" else value
        if celsius < -273.15 - 1e-10:
            raise ValueError("Temperature cannot be below absolute zero.")
        result = celsius * 9 / 5 + 32 if target == "f" else celsius + 273.15 if target == "k" else celsius
    else:
        units = UNITS.get(category, {})
        if source not in units or target not in units:
            raise ValueError("Choose units from the displayed list.")
        result = value * (units[source] / units[target])
    if not math.isfinite(result):
        raise ValueError("The converted value is too large.")
    return result


def converter() -> None:
    heading("UNIT CONVERTER")
    categories = [*UNITS, "temperature"]
    for index, name in enumerate(categories, 1):
        print(f"  [{index}] {name.title()}")
    category = categories[integer("Category", 1, 1, len(categories)) - 1]
    print("  Units: " + ("C, F, K" if category == "temperature" else ", ".join(UNITS[category])))
    if category == "data":
        print("  All data units are bytes; KB is decimal, KiB is binary.")
    value = number("Value")
    source, target = ask("From unit"), ask("To unit")
    print(paint(f"  {value:.12g} {source} = {convert(value, category, source, target):.12g} {target}", "92"))


def generate_password(length: int, groups: list[str]) -> str:
    if not groups or any(not group for group in groups):
        raise ValueError("Select at least one nonempty character group.")
    if not max(4, len(groups)) <= length <= 128:
        raise ValueError("Password length must be 4 to 128 and fit all selected groups.")
    characters = [secrets.choice(group) for group in groups]
    pool = "".join(groups)
    characters.extend(secrets.choice(pool) for _ in range(length - len(characters)))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


def passwords() -> None:
    heading("PASSWORD GENERATOR")
    length = integer("Length", 20, 4, 128)
    groups = []
    for label, group in [("Lowercase letters", string.ascii_lowercase),
                         ("Uppercase letters", string.ascii_uppercase),
                         ("Numbers", string.digits),
                         ("Symbols", "!@#$%^&*()-_=+[]{}:,.?")]:
        if yes(label):
            groups.append(group)
    print(paint("  " + generate_password(length, groups), "92"))
    print("  Generated locally with secure randomness; visible in terminal history.")


def text_tools() -> None:
    heading("TEXT TOOLS")
    print("  Paste or type text. A line containing only . finishes input.")
    lines = []
    while True:
        line = input("  > ")
        if line == ".":
            break
        lines.append(line)
    text = "\n".join(lines)
    print(paint(f"  {len(text)} characters | {len(text.split())} words | {len(lines)} lines", "92"))
    print("  [1] UPPERCASE  [2] lowercase  [3] Title Case  [4] Reverse  [5] Stats only")
    action = integer("Action", 5, 1, 5)
    transforms = {1: str.upper, 2: str.lower, 3: str.title, 4: lambda value: value[::-1]}
    if action in transforms:
        print("\n" + transforms[action](text))


def randomizer() -> None:
    heading("DICE & RANDOM CHOICE")
    print("  [1] Roll dice  [2] Flip a coin  [3] Pick from a list")
    action = integer("Action", 1, 1, 3)
    if action == 1:
        count = integer("Number of dice", 2, 1, 100)
        sides = integer("Sides per die", 6, 2, 1000000)
        rolls = [secrets.randbelow(sides) + 1 for _ in range(count)]
        print(paint(f"  Rolls: {', '.join(map(str, rolls))}\n  Total: {sum(rolls)}", "92"))
    elif action == 2:
        print(paint("  " + secrets.choice(["Heads", "Tails"]), "92"))
    else:
        choices = [item.strip() for item in ask("Choices, separated by commas").split(",") if item.strip()]
        if len(choices) < 2:
            raise ValueError("Enter at least two choices separated by commas.")
        print(paint("  Selected: " + secrets.choice(choices), "92"))


def countdown() -> None:
    heading("COUNTDOWN")
    seconds = integer("Duration in seconds", 60, 1, 86400)
    print("  Press Ctrl+C to cancel.")
    deadline = time.monotonic() + seconds
    previous = None
    while True:
        remaining = max(0, math.ceil(deadline - time.monotonic()))
        if remaining != previous:
            hours, rest = divmod(remaining, 3600)
            minutes, secs = divmod(rest, 60)
            print(f"\r  {hours:02}:{minutes:02}:{secs:02}", end="", flush=True)
            previous = remaining
        if remaining == 0:
            break
        time.sleep(min(.1, max(0, deadline - time.monotonic())))
    print(paint("\n  Time's up!", "92"))


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_hasher() -> None:
    heading("FILE FINGERPRINT / SHA-256")
    path = Path(ask("File path").strip('"')).expanduser()
    print("  Reading file...")
    print(paint("  SHA-256: " + hash_file(path), "92"))
    print("  Matching hashes can verify that two files have identical contents.")


TOOLS = [
    ("Calculator", "Expressions, functions & previous answer", calculator),
    ("Unit converter", "Length, mass, time, data & temperature", converter),
    ("Password generator", "Secure randomness, custom character groups", passwords),
    ("Text tools", "Word counts, case changes & reverse", text_tools),
    ("Dice & random choice", "Roll, flip or let chance pick", randomizer),
    ("Countdown timer", "A simple timer up to 24 hours", countdown),
    ("File fingerprint", "Stream a file's SHA-256 checksum", file_hasher),
]


def main() -> None:
    while True:
        try:
            heading("P O C K E T K I T   /   Python multitool")
            for index, (name, description, _) in enumerate(TOOLS, 1):
                print(f"  {paint(f'[{index}]')} {name:<21} {description}")
            print(f"  {paint('[0]')} Exit")
            choice = ask("Choose a tool").lower()
            if choice in {"0", "q", "quit", "exit"}:
                break
            if choice not in {str(index) for index in range(1, len(TOOLS) + 1)}:
                print(paint("  Choose one of the numbers above.", "93"))
                continue
            try:
                TOOLS[int(choice) - 1][2]()
            except (ValueError, OSError) as exc:
                print(paint(f"  {exc}", "93"))
            except KeyboardInterrupt:
                print("\n  Tool cancelled.")
            input("\n  Press Enter to return to the menu...")
        except (EOFError, KeyboardInterrupt):
            break
    print("\n  Thanks for using PocketKit. See you!\n")


if __name__ == "__main__":
    main()
