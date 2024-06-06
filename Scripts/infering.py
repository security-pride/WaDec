import torch,re,os
from transformers import AutoModelForCausalLM, BitsAndBytesConfig, AutoTokenizer, GenerationConfig
from peft import PeftModel
from Utils.WatModuleParcer import WatModule
from tree_sitter import Language, Parser
from Utils.formatting import formated_c
import argparse
C_LANGUAGE = Language('Metrics/Codebleu/so/my-languages.so', 'c')
parser = Parser()
parser.set_language(C_LANGUAGE)
device = "cuda:1"  

def parse_arguments():
    parser = argparse.ArgumentParser(description='Infering')
    parser.add_argument('--base_model', type=str, required= True, help='model from huggingface or disk')
    parser.add_argument('--wat_path', type=str, help='Path to the wat code file')
    parser.add_argument('--dst_path', type=str, required= True, help='Path to the wat code file')
    parser.add_argument('--invoke', type=str, required= True, help='Invoke functions(e.g. func1,fun2,func3)')
    return parser.parse_args()

def load_model(args):
    base_model = args.base_model
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=BitsAndBytesConfig(load_in_8bit=True),
        torch_dtype=torch.float16,
        device_map=device
    )
    return model, tokenizer


def get_declaration(wat_block_str:str, wat_module:WatModule):
    func_declareation_pat = re.compile(r'\s+call ([\S\$]+)[\)\n]+')
    call_func_declarations = []
    for call_func_id in func_declareation_pat.findall(wat_block_str):
        if call_func_id.startswith('$'):
            call_func_id = re.escape(call_func_id) 
        pat_func_call_declaration = re.compile(rf'(  \(func {call_func_id} .*?\))\n')
        match = pat_func_call_declaration.search(wat_module.content)
        if match:
            call_func_declaration = match.group(1)
            if call_func_declaration in call_func_declarations:
                continue
            call_func_declarations.append(call_func_declaration)
    return '\n'.join(call_func_declarations)

def is_error(c_text: str) -> bool:
    root_node = parser.parse(bytes(c_text, 'utf8')).root_node
    return root_node.has_error

def get_prompt(wat_block_str:str, wat_module:WatModule):
    return f"""
### Instruction:
Decompile the provided WAT snippet into an equivalent C code snippet, ensuring:
- Logical structure and functionality match the original WAT code.
- '<< >>' markers are preserved to indicate incomplete segments.
- Replace strings in the decompiled C code with their WAT data segment offsets. The format to represent these strings should be '(i32|i64.const offset)'.
- For variables in the decompiled C snippet, name them based on the value of the offset in wat snippet (i.e., i32.load offset=xxx), local variables are named local_{{offset}}.
- Even if the part of wat code is dead code, decompile it to c.

### Input(wat code):
The `Call_Func Declaration` specifies the number of params and return values
[Call_Func Declarations]
{get_declaration(wat_block_str, wat_module)}
[/Call_Func Declarations]
[Wat]
{wat_block_str}
[/Wat]
### Response:
"""

def CLM_decompile(
    wat_path:str,
    invoke_list:list[str],
    model, 
    tokenizer,
    max_str_len:int = 2000,
    max_new_tokens=8000,
    ):
    rodata_pat = re.compile(r'\$\.\w+ \(\w\d+\.const (\d+)\)')
    wat_module = WatModule()
    wat_module.parse_wat(wat_path,max_block_str_len=max_str_len)
    blocks = wat_module.blocks
    ordered_funcs = wat_module.get_ordered_funcs(invoke_list=invoke_list)
    Decompile_result = []
    error_funcs = []
    for i, wat_func_id in enumerate(ordered_funcs):
        wat_func_blocks:dict = blocks[wat_func_id]
        func_c = ''
        for i, (wat_block_id, wat_block_str) in enumerate(wat_func_blocks.items()):
            eval_prompt = get_prompt(wat_block_str, wat_module)
            if len(eval_prompt) > 8000:
                print('Too long input(8000)')
                break
            block_dict = wat_module.get_const_strs(wat_block_str)
            model_input = tokenizer(eval_prompt, return_tensors="pt").to(device)
            model_input = {key: value for key, value in model_input.items()}
            model.eval()            
            with torch.no_grad():
                generated_tokens = model.generate(
                    **model_input, 
                    max_new_tokens=max_new_tokens,
                    use_cache=True,
                    pad_token_id=tokenizer.eos_token_id
                )
                decoded_output = tokenizer.decode(generated_tokens[0].cpu().numpy(), skip_special_tokens=True)
            block_c = decoded_output[decoded_output.index("### Response:")+14:]
            for key, val in block_dict.items():
                block_c = block_c.replace(key,val.replace('\\0a','\\n'))
            matches = rodata_pat.finditer(block_c)
            for match in matches:
                number = int(match.group(1))
                if number >=  65536:
                    continue
                block_c = block_c.replace(match.group(),chr(number))
            if i == 0:
                func_c += block_c
            elif wat_block_id.startswith('$'):
                func_c = func_c.replace(f"<< {wat_block_id[1:]} >>",block_c)
            else:
                func_c = func_c.replace(f"<< {wat_block_id[2:-2]} >>",block_c)
        if is_error(func_c):
            error_funcs.append(i)
        Decompile_result.append(func_c)
    return '\n'.join(Decompile_result), \
        not error_funcs, \
        '\n'.join([x for j, x in enumerate(Decompile_result) if j not in error_funcs])
     


def main():
    args = parse_arguments()
    model, tokenizer = load_model(args=args)
    result, _, _ = CLM_decompile(
        wat_path = args.wat_path,
        invoke_list = [f'${i.strip()}' for i in args.invoke.split(',')],
        model = model,
        tokenizer = tokenizer
    )
    res = formated_c(result)
    open(args.dst_path,'w').write(res)
    print(args.dst_path)

if __name__ == '__main__':
    main()