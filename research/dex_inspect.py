import zipfile, struct, sys

def parse_dex(dex):
    magic = dex[:8]
    string_ids_size, string_ids_off = struct.unpack_from('<II', dex, 0x38)
    type_ids_size, type_ids_off = struct.unpack_from('<II', dex, 0x40)
    proto_ids_size, proto_ids_off = struct.unpack_from('<II', dex, 0x48)
    field_ids_size, field_ids_off = struct.unpack_from('<II', dex, 0x50)
    method_ids_size, method_ids_off = struct.unpack_from('<II', dex, 0x58)
    class_defs_size, class_defs_off = struct.unpack_from('<II', dex, 0x60)

    # Parse string offsets
    string_offsets = struct.unpack_from(f'<{string_ids_size}I', dex, string_ids_off)

    def get_string(idx):
        off = string_offsets[idx]
        # skip uleb128 length
        while (dex[off] & 0x80) != 0:
            off += 1
        off += 1
        end = dex.find(b'\x00', off)
        return dex[off:end].decode('utf-8', errors='replace')

    # Parse type IDs
    type_type_idx = struct.unpack_from(f'<{type_ids_size}I', dex, type_ids_off)
    def get_type(idx):
        return get_string(type_type_idx[idx])

    # Parse method IDs
    methods = []
    for i in range(method_ids_size):
        class_idx, proto_idx, name_idx = struct.unpack_from('<HHI', dex, method_ids_off + i * 8)
        methods.append((class_idx, proto_idx, name_idx))

    def get_method(idx):
        class_idx, proto_idx, name_idx = methods[idx]
        return get_type(class_idx), get_string(name_idx)

    # Parse class defs
    classes = {}
    for i in range(class_defs_size):
        class_idx, access_flags, superclass_idx, interfaces_off, source_file_idx, annotations_off, class_data_off, static_values_off = struct.unpack_from('<IIIIIIII', dex, class_defs_off + i * 32)
        cname = get_type(class_idx)
        sname = get_type(superclass_idx) if superclass_idx != 0xFFFFFFFF else "None"
        classes[cname] = {'super': sname, 'data_off': class_data_off}

    return get_string, get_type, get_method, classes

with zipfile.ZipFile('/Users/yashpal/Documents/rom/research/SystemUIGoogle.apk', 'r') as z:
    for dex_name in ['classes.dex', 'classes2.dex', 'classes3.dex']:
        dex = z.read(dex_name)
        get_string, get_type, get_method, classes = parse_dex(dex)
        print(f"=== {dex_name}: {len(classes)} classes ===")
        for cname in sorted(classes.keys()):
            if any(k in cname for k in ['AxBlur', 'BlurEngine', 'BlurTile', 'WindowRootViewBlur', 'BlurChoreographer']):
                print(f"  Class: {cname} (extends {classes[cname]['super']})")
