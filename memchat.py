import streamlit as st
from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationEntityMemory
from langchain.chains.conversation.prompt import ENTITY_MEMORY_CONVERSATION_TEMPLATE
from langchain.llms import OpenAI
import argparse
from dataclasses import dataclass
from langchain.vectorstores.chroma import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

# Set Streamlit page configuration
st.set_page_config(page_title='DHV MemBot', layout='wide')


CHROMA_PATH = "chroma"

PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}
"""

# Initialize session states
if "generated" not in st.session_state:
    st.session_state["generated"] = []
if "past" not in st.session_state:
    st.session_state["past"] = []
if "input" not in st.session_state:
    st.session_state["input"] = ""
if "stored_session" not in st.session_state:
    st.session_state["stored_session"] = []

# Define function to get user input
def get_text():
    """
    Get the user input text.

    Returns:
        (str): The text entered by the user
    """
    input_text = st.text_input("You: ", st.session_state["input"], key="input",
                            placeholder="คำถาม/คำกล่าว...", 
                            label_visibility='hidden')
    return input_text

# Define function to start a new chat
def new_chat():
    """
    Clears session state and starts a new chat.
    """
    save = []
    for i in range(len(st.session_state['generated'])-1, -1, -1):
        save.append("User:" + st.session_state["past"][i])
        save.append("Bot:" + st.session_state["generated"][i])        
    st.session_state["stored_session"].append(save)
    st.session_state["generated"] = []
    st.session_state["past"] = []
    st.session_state["input"] = ""
    st.session_state["entity_memory"].entity_store = {}
    st.session_state["entity_memory"].buffer.clear()

MODEL = 'gpt-3.5-turbo'
K = 3

# Set up the Streamlit app layout
st.title("DHV AI Startup Membot Demo")
st.subheader("ประเมินความเสี่ยงโรคใน Total Health Care")

# Ask the user to enter their OpenAI API key
OPENAI_API_KEY = ""

# Session state storage would be ideal
if OPENAI_API_KEY:
    # Create an OpenAI instance
    llm = OpenAI(temperature=0,
                api_key=OPENAI_API_KEY , 
                model_name=MODEL, 
                verbose=False) 

    # Create a ConversationEntityMemory object if not already created
    if 'entity_memory' not in st.session_state:
            st.session_state["entity_memory"] = ConversationEntityMemory(llm=llm, k=K )
        
    # Create the ConversationChain object with the specified configuration
    Conversation = ConversationChain(
            llm=llm, 
            prompt=ENTITY_MEMORY_CONVERSATION_TEMPLATE,
            memory=st.session_state["entity_memory"]
        )  
else:
    st.sidebar.warning('API key required to try this app. The API key is not stored in any form.')
    # st.stop()

# Add a button to start a new chat
#st.sidebar.button("New Chat", on_click=new_chat, type='primary')

# Get the user input
user_input = get_text()

# Generate the output using the ConversationChain object and the user input, and add the input/output to the session
if user_input:
    output = Conversation.run(input=user_input)  
    st.session_state["past"].append(user_input)  
    st.session_state["generated"].append(output)  

    # Prepare the DB.
    embedding_function = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)

    # Search the DB.
    results = db.similarity_search_with_relevance_scores(user_input, k=3)
    if not results or (results and results[0][1] < 0.7):
        st.write("???")
        #return

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=user_input)
    st.write(prompt)

    model = ChatOpenAI()
    response_text = model.predict(prompt)

    sources = [doc.metadata.get("source", None) for doc, _score in results]
    formatted_response = f"<span style='color:red'>{response_text}</span>\nSources: {sources}"
    st.write(formatted_response, unsafe_allow_html=True)

# Allow to download as well
download_str = []
# Display the conversation history using an expander, and allow the user to download it
with st.expander("บทสนทนา", expanded=True):
    for i in range(len(st.session_state['generated'])-1, -1, -1):
        st.info(st.session_state["past"][i], icon="🧐")
        st.success(st.session_state["generated"][i], icon="🤖")
        download_str.append(st.session_state["past"][i])
        download_str.append(st.session_state["generated"][i])
    
    # Can throw error - requires fix
    download_str = '\n'.join(download_str)
    if download_str:
        st.download_button('บันทึกบทสนทนา', download_str)

# Display stored conversation sessions in the sidebar
for i, sublist in enumerate(st.session_state["stored_session"]):
        with st.sidebar.expander(label=f"Conversation-Session:{i}"):
            st.write(sublist)

# Allow the user to clear all stored conversation sessions
if st.session_state["stored_session"]:   
    if st.sidebar.checkbox("Clear-all"):
        del st.session_state["stored_session"]