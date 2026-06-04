import io
import os
import numpy as np
import soundfile as sf
import httpx

from utils import ConfigManager

GRANITE_MODEL = "ibm-granite/granite-speech-4.1-2b"

DEFAULT_TASK_PROMPT = (
    "Transcribe the speech with proper punctuation and capitalization. "
    "The speaker is a software engineer dictating technical content; expect "
    "terms like vLLM, CUDA, PyTorch, NumPy, Anthropic, snake_case identifiers "
    "such as vllm_worker_setup_signals() or train_main(), file paths like "
    "script.py or src/main.py, and shell commands."
)


def _build_prompt(processor):
    task = DEFAULT_TASK_PROMPT
    extra = ConfigManager.get_config_value('model_options', 'initial_prompt')
    if extra:
        task = f"{task} Additional context: {extra}"
    chat = [{"role": "user", "content": f"<|audio|>{task}"}]
    return processor.tokenizer.apply_chat_template(
        chat, tokenize=False, add_generation_prompt=True)


def create_local_model():
    """Load the Granite Speech model and processor onto the GPU."""
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    ConfigManager.console_print(f'Loading {GRANITE_MODEL}...')
    processor = AutoProcessor.from_pretrained(GRANITE_MODEL)
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        GRANITE_MODEL, device_map="cuda", torch_dtype=torch.bfloat16)
    ConfigManager.console_print('Granite model loaded.')
    return model, processor


def transcribe_local(audio_data, local_model=None):
    """Transcribe an int16 numpy array with the local Granite model."""
    import torch
    if not local_model:
        local_model = create_local_model()
    model, processor = local_model

    wav = torch.from_numpy(audio_data.astype(np.float32) / 32768.0).unsqueeze(0)
    prompt = _build_prompt(processor)
    inputs = processor(prompt, wav, device="cuda", return_tensors="pt").to("cuda")
    out = model.generate(**inputs, max_new_tokens=200, do_sample=False, num_beams=1)
    n = inputs["input_ids"].shape[-1]
    return processor.tokenizer.batch_decode(out[:, n:], skip_special_tokens=True)[0]


def transcribe_remote(audio_data):
    """Send audio to the local transcription server (reached via SSH tunnel) and return raw text."""
    byte_io = io.BytesIO()
    sample_rate = ConfigManager.get_config_section('recording_options').get('sample_rate') or 16000
    sf.write(byte_io, audio_data, sample_rate, format='wav')
    byte_io.seek(0)

    try:
        response = httpx.post('http://localhost:47892/transcribe', content=byte_io.read(), timeout=30.0)
        response.raise_for_status()
        return response.json()['text']
    except httpx.ConnectError:
        raise RuntimeError('Could not connect to transcription server at localhost:47892 — is the SSH tunnel up?')
    except Exception as e:
        raise RuntimeError(f'Remote transcription failed: {e}')


def post_process_transcription(transcription):
    transcription = transcription.strip()
    post_processing = ConfigManager.get_config_section('post_processing')
    if post_processing['remove_trailing_period'] and transcription.endswith('.'):
        transcription = transcription[:-1]
    if post_processing['add_trailing_space']:
        transcription += ' '
    if post_processing['remove_capitalization']:
        transcription = transcription.lower()
    return transcription


def transcribe(audio_data, local_model=None):
    """Transcribe audio using the remote server or the local Granite model."""
    if audio_data is None:
        return ''
    if os.environ.get('WW_USE_REMOTE'):
        transcription = transcribe_remote(audio_data)
    else:
        transcription = transcribe_local(audio_data, local_model)
    return post_process_transcription(transcription)
