def count_key_value(array_of_dicts, key, value):
    count = 0
    for d in array_of_dicts:
        dictValue = d.get(key)
        if dictValue == value:
            count += 1
    return count
