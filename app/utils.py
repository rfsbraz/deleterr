def print_readable_freed_space(saved_space):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    index = 0
    
    while saved_space >= 1024 and index < len(units) - 1:
        saved_space /= 1024
        index += 1
    
    return f"{saved_space:.2f} {units[index]}"

def parse_size_to_bytes(size_str):
    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    unit = ''.join([i for i in size_str if not i.isdigit() and not i == '.'])
    size = ''.join([i for i in size_str if i.isdigit() or i == '.'])
    size = float(size)
    index = units.index(unit)
    
    while index > 0:
        size *= 1024
        index -= 1
    
    return int(size)