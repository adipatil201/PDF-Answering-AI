import time
import streamlit as st
from PyPDF2 import PdfReader
from langchain import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.llms import LlamaCpp


def text_string(file):
    text_from_file = ""
    pdf_reader = PdfReader(file)
    for page in pdf_reader.pages:
        text_from_file += page.extract_text()
    return text_from_file


def chunking_func(text):
    chunking_obj = RecursiveCharacterTextSplitter(
        chunk_size = 1024,
        chunk_overlap = 100,
        length_function = len
    )
    chunked_text = chunking_obj.split_text(text)
    return chunked_text


def vectorDB(chunked_text):
    text_embed_model = HuggingFaceEmbeddings(
        model_name = 'intfloat/multilingual-e5-base',  # 'intfloat/multilingual-e5-base'  "thenlper/gte-large"
        model_kwargs = {'device' : 'cpu'},
        encode_kwargs = {'normalize_embeddings' : True}
    )
    vectorDB = FAISS.from_texts(texts = chunked_text, embedding = text_embed_model)
    return vectorDB


def response_chain_builder(knowledge_base):
    mistral = LlamaCpp(
        streaming = False,
        n_gpu_layers = -1,
        n_batch = 512,
        max_tokens = 800,
        model_path = "/content/mistral-7b-instruct-v0.2.Q5_K_M.gguf", 
        temperature = 0.3,
        top_p = 0.5,
        verbose = False,
        n_ctx = 8192
    )

    chat_memory = ConversationBufferMemory(memory_key = 'chat_history', return_messages = True)

    template = ("""
    You are a dedicated Document Assistant Chatbot. You will help in making the most of given documents. You can:
                
    1. **Summarize Documents:** Get a concise overview of the key points of the given documents.
    2. **Find Specific Information:** Locate specific details or data within the given documents.
    3. **Explain Complex Sections:** Simplify difficult-to-understand parts.
    4. **Highlight Important Sections:** Identify key findings or critical clauses.
    5. **Answer Questions:** Answer the questions based on the given documents and the conversation.
                
    **Chat_History:**
    {chat_history}
    **Question:**
    {question}

    IMPORTANT REMARKS
    - If the question is a chitchat question or lets say a compliment from user's side, then dont use the context to answer those questions. Rather answer it like a normal person would.
    - Give a well ORGANISED OUTPUT with proper headings numerical pointers whenever possible
    - Your tone should always be PROFESSIONAL and ARTICULATE, yet HUMAN-LIKE.
    """)

    final_prompt = PromptTemplate.from_template(template)

    response_chain = ConversationalRetrievalChain.from_llm(
        llm = mistral,
        retriever = knowledge_base.as_retriever(search_kwargs={"k": 4}),
        memory = chat_memory,
        condense_question_prompt = final_prompt
    )

    return response_chain


def data_streamer(answer):
    for char in answer:
        yield char
        time.sleep(0.01)
        

st.title("Mistral PDF AI")

st.sidebar.header("Upload your PDF")
uploaded_file = st.sidebar.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    st.sidebar.write("PDF successfully uploaded!")

    if st.sidebar.button("Process"):

        if "conversation_chain" not in st.session_state:
            with st.spinner("Processing"):

                pdf_text = text_string(uploaded_file)

                chunked_text = chunking_func(pdf_text)

                knowledge_base = vectorDB(chunked_text)

                st.session_state["conversation_chain"] = response_chain_builder(knowledge_base)

                st.sidebar.write('Start chatting....')


if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask you question"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response = st.session_state["conversation_chain"]({'question': prompt})
        st.write_stream(data_streamer(response['answer']))
        
    st.session_state.messages.append({"role": "assistant", "content": response['answer']})