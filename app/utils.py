valid_units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]


def print_readable_freed_space(saved_space):
    index = 0

    while saved_space >= 1024 and index < len(valid_units) - 1:
        saved_space /= 1024
        index += 1

    return f"{saved_space:.2f} {valid_units[index]}"


def parse_size_to_bytes(size_str):
    unit = "".join([i for i in size_str if not i.isdigit() and i != "."]).strip()
    size = "".join([i for i in size_str if i.isdigit() or i == "."])
    size = float(size)
    index = valid_units.index(unit)

    while index > 0:
        size *= 1024
        index -= 1

    return int(size)


def validate_units(threshold):
    unit = "".join([i for i in threshold if not i.isdigit() and i != "."]).strip()

    if unit not in valid_units:
        raise ValueError(f"Invalid unit '{unit}'. Valid units are {valid_units}")
