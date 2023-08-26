def print_readable_freed_space(saved_space):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    index = 0
    
    while saved_space >= 1024 and index < len(units) - 1:
        saved_space /= 1024
        index += 1
    
    return f"{saved_space:.2f} {units[index]}"