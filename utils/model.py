import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline,GenerationConfig, BitsAndBytesConfig
from config.config import settings

# Llama-3.1-8B 최적화된 양자화 설정
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",           # NF4 양자화 
    bnb_4bit_compute_dtype=torch.bfloat16, 
    bnb_4bit_use_double_quant=True,      
)

# 토크나이저 로드 (Llama-3.1 최적화)
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B-Instruct", token=settings.hf_token)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "left"  # Llama에서 권장

# 모델 로드 (MIG 환경 최적화)
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3.1-8B-Instruct",
    token=settings.hf_token,
    quantization_config=quantization_config,
    device_map="auto",
    torch_dtype=torch.bfloat16,
    max_memory={0: "18GB"},  # MIG 2g-20GB 환경에서 안전한 할당
    trust_remote_code=True,
    attn_implementation="flash_attention_2"  # Flash Attention으로 속도 향상
)


try:
    if not hasattr(model, 'quantization_config'):
        model = torch.compile(model, mode="reduce-overhead")
    else:
        print("양자화된 모델에서는 torch.compile을 건너뜁니다.")
except Exception as e:
    print(f"torch.compile 적용 실패: {e}")

# Llama-3.1 Chat Template 함수
def format_llama_prompt(prompt: str) -> str:
    """Llama-3.1 Chat Template 적용"""
    return f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>

{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

def generate_simulation_result(prompt: str):
    try:
        # Llama-3.1 Chat Template 적용
        formatted_prompt = format_llama_prompt(prompt)
        
        inputs = tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=2048)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=2048,
                do_sample=True,
                temperature=0.7,  # Llama-3.1에 최적화된 값
                top_p=0.9,
                repetition_penalty=1.1,
                num_beams=1,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
                use_cache=True  # 속도 향상
            )
        
        full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Chat template 제거하고 응답만 추출
        if "<|start_header_id|>assistant<|end_header_id|>" in full_text:
            return full_text.split("<|start_header_id|>assistant<|end_header_id|>")[-1].strip()
        elif full_text.startswith(formatted_prompt):
            return full_text[len(formatted_prompt):].strip()
        else:
            return full_text
            
    except Exception as e:
        return f"야구 시뮬레이션 생성 중 오류가 발생했습니다: {str(e)}"

def detect_profanity(prompt: str):
    try:
        formatted_prompt = format_llama_prompt(prompt)
        inputs = tokenizer(formatted_prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False,
                temperature=0.1,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        if "<|start_header_id|>assistant<|end_header_id|>" in full_text:
            result = full_text.split("<|start_header_id|>assistant<|end_header_id|>")[-1].strip()
        else:
            result = full_text[len(formatted_prompt):].strip() if full_text.startswith(formatted_prompt) else full_text
        
        return result
            
    except Exception as e:
        return '{"isCurse": false, "words": []}'

def generate_text(prompt: str, max_tokens: int = 1024) -> str:
    formatted_prompt = format_llama_prompt(prompt)
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=0.7,  # Llama-3.1 최적화 값
            top_p=0.9,
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            use_cache=True
        )
    
    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Chat template 응답 부분만 추출
    if "<|start_header_id|>assistant<|end_header_id|>" in full_output:
        result_only = full_output.split("<|start_header_id|>assistant<|end_header_id|>")[-1].strip()
    else:
        result_only = full_output[len(formatted_prompt):].strip()
    
    return result_only

# Llama-3.1 최적화된 Generation Config
model.generation_config = GenerationConfig(
    do_sample=True,
    temperature=0.7,  # Llama-3.1에 최적화된 값
    top_p=0.9,
    max_new_tokens=2048,
    repetition_penalty=1.1,
    pad_token_id=tokenizer.eos_token_id,
    eos_token_id=tokenizer.eos_token_id,
    use_cache=True
)



