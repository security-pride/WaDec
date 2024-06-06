import lizard
def get_CCN_SCORE(original_path, decompiled_path,mode = 1):
    original_analysis_results = lizard.analyze_file(original_path)
    decompiled_analysis_results = lizard.analyze_file(decompiled_path)

    original_map = {}
    decompiled_map = {}

    for function in original_analysis_results.function_list:
        name = function.name
        original_map[name] = {
            "cyclomatic_complexity" : function.cyclomatic_complexity,
            "parameter_count" : function.parameter_count,
            "code_line" : function.nloc,
        }
    for function in decompiled_analysis_results.function_list:
        name = function.name
        if '0x2Ewasm_' in name:
            name = name.split('0x2Ewasm_')[-1]
            if name in ['0x5F_original_main','0x5F_main_void']:
                name = 'main'
        else:
            for i in original_map.keys():
                if name.endswith(f'_{i}'):
                    name = i
                    break                    
        decompiled_map[name] = {
            "cyclomatic_complexity" : function.cyclomatic_complexity,
            "parameter_count" : function.parameter_count,
            "code_line" : function.nloc,
        }
    count = 0
    decompiled_code_line = 0
    original_code_line = 0
    for func_name, decompiled_item in decompiled_map.items():
        decompiled_code_line += decompiled_item['code_line']
        if func_name == '__original_main':
            func_name = 'main'
        if func_name.startswith('export::'):
            func_name = func_name[8:]
        if func_name not in original_map.keys():
            continue
        original_item = original_map[func_name]
        original_code_line += original_item['code_line']
        if original_item == decompiled_item:
            count += 1
        elif original_item["cyclomatic_complexity"] == decompiled_item["cyclomatic_complexity"]:
                count += 0.8
        elif original_item['parameter_count'] == decompiled_item['parameter_count']:
            count += 0.2
    score = count/len(original_map)
    if original_code_line == 0:
        print()
    flation = (decompiled_code_line - original_code_line)/original_code_line
    return score, flation


if __name__ == "__main__":
    original_path = '/home/sxy/wasm2c/z_test/b_test/b.c'
    decompiled_path = '/home/sxy/wasm2c/z_test/b_test/b_decompiled.c'
    print(get_CCN_SCORE(original_path, decompiled_path))