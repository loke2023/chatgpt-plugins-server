from typing import List
import openai
from models.models import ChatCompletionMessage
import os


from tenacity import retry, wait_random_exponential, stop_after_attempt


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Embed texts using OpenAI's ada model.

    Args:
        texts: The list of texts to embed.

    Returns:
        A list of embeddings, each of which is a list of floats.

    Raises:
        Exception: If the OpenAI API call fails.
    """ 
 
    # Call the OpenAI API to get the embeddings
    response = openai.Embedding.create(input=texts, model="text-embedding-ada-002") 

    # Extract the embedding data from the response
    data = response["data"]  # type: ignore

    # Return the embeddings as a list of lists of floats
    return [result["embedding"] for result in data]


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def get_chat_completion(
    messages,
    model="gpt-3.5-turbo",  # use "gpt-4" for better results
):
    """
    Generate a chat completion using OpenAI's chat completion API.

    Args:
        messages: The list of messages in the chat history.
        model: The name of the model to use for the completion. Default is gpt-3.5-turbo, which is a fast, cheap and versatile model. Use gpt-4 for higher quality but slower results.

    Returns:
        A string containing the chat completion.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    # call the OpenAI chat completion API with the given messages
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
    )

    choices = response["choices"]  # type: ignore
    completion = choices[0].message.content.strip()
    print(f"Completion: {completion}")
    return completion


@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(3))
def get_chat_completion_for_prompt( 
    prompt, 
    query,
    model="gpt-3.5-turbo",  # use "gpt-4" for better results
):
    """
    Generate a chat completion using OpenAI's chat completion API.

    Args:
        messages: The list of messages in the chat history.
        model: The name of the model to use for the completion. Default is gpt-3.5-turbo, which is a fast, cheap and versatile model. Use gpt-4 for higher quality but slower results.

    Returns:
        A string containing the chat completion.

    Raises:
        Exception: If the OpenAI API call fails.
    """
    # call the OpenAI chat completion API with the given messages
    
    messages = []
    messages.append({"role":"user", "content": prompt}) 
    if query:
        messages.append({"role":"user", "content": query})
    
    print("real call chat completion, messages:", messages) 

    response = openai.ChatCompletion.create(
        model=model, 
        messages=messages,
    ) 
      
    choices = response["choices"]  # type: ignore
    completion = choices[0].message.content.strip()
    print(f"Completion: {completion}")
    return completion
 

def construct_prompt(context_embeddings) -> str:
    """
    Fetch relevant 
    """ 

    chosen_sections = []
    chosen_sections_ids = [] 
     
    for r in context_embeddings:
        # 第一层 QueryResult 对象 
        for rr in r.results:     
            # 第二层 DocumentChunkWithScore 对象
            if rr.id not in chosen_sections_ids: 
                chosen_sections_ids.append(rr.id)
                chosen_sections.append(rr.text)
            
    print("chosen_sections:", chosen_sections)
    result = """你拥有非常多的知识，我现在给你一些提示如下: \n{}, 
        请你回答一些问题，如果你不知道那么就回答“不知道”,""".format(chosen_sections)
    
    return result


def construct_prompt_tips(context_embeddings, role, msg) -> str:
    """
    Fetch relevant 
    """ 

    chosen_sections = []
    chosen_sections_ids = [] 
    chosen_sections.append({
        "role": "user",
        "content": "你是一个中文语言学家，拥有非常多知识的得力助手"
    }) 

    for r in context_embeddings:
        # 第一层 QueryResult 对象 
        for rr in r.results:     
            # 第二层 DocumentChunkWithScore 对象
            if rr.id not in chosen_sections_ids: 
                chosen_sections_ids.append(rr.id) 
                chosen_sections.append({
                    "role": "user", 
                    "content": rr.text}
                    ) 
 
    chosen_sections.append({
        "role": "user",
        "content": "请帮我重新整理上面几段的内容"
    })
    
    chosen_ret = get_chat_completion(chosen_sections)
            
    print("tips chosen_sections:{}, chosen_ret:{}".format(chosen_sections, chosen_ret))
    result = """你是一个{}，你拥有非常多的知识，我现在给你一些提示如下: \n{}, \n\n
    请帮我重写下面这段内容：{}""".format(role, chosen_ret, msg)
    
    return result