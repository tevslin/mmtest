import os

import streamlit as st
import mm_agent
st.session_state['test']=True #changes appearance of sidebar
st.session_state["version"]="0.0.2"
st.set_page_config(layout="wide")

def save_file_dialog(file_object,suggested_file_name):
    import mimetypes
    
    mime_type, _ = mimetypes.guess_type(suggested_file_name)
    if mime_type is None:
        mime_type = "application/octet-stream"  # Default MIME type for binary file
    st.download_button(
        label="Download File",
        data=file_object,
        file_name=suggested_file_name,
        mime=mime_type
    )
    
def process_form(form_number,article):
    def set_s3():
        print('setting s3 values')
        st.session_state["newvalues"]["transcript"]=st.query_params["transcript"]
        st.session_state["newvalues"]["pickle"]=st.query_params['pickle']
        st.session_state["newvalues"]["video"]=st.query_params['video']
        del st.session_state.newvalues["next"]
        
    def set_value():
        print("set value",st.session_state.url)
        st.session_state["newvalues"]["url"]=st.session_state.url
        del st.session_state.newvalues["next"]
        
    def set_file():
        st.session_state["newvalues"].update({"raw":st.session_state.input_file.getvalue(),
                                     "file_name":st.session_state.input_file.name})
        
        del st.session_state.newvalues["next"]
    def do_first_dialog():
        words_in_article = st.slider("Words in article", 500, 4000, 1000)
        #st.write("Query Parameters:", st.query_params)
        if st.query_params and "transcript" in st.query_params and "pickle" in st.query_params and "video" in st.query_params:
            st.session_state['passed_files']='yes'
            st.write(f"processing {st.query_params['transcript']} and {st.query_params['pickle']}")
        else:         
            source_document = st.radio("Retrieve source document from:", ["the internet", "my computer"]) 
        # Buttons and logic
        if st.button('OK'):
            if "passed_files" in st.session_state:
                st.session_state['newvalues']={'origin':"s3",
                                           "words":words_in_article,"next":True}
            else:                
                st.session_state['newvalues']={'origin':"internet" if source_document=="the internet" else "upload",
                                           "words":words_in_article,"next":True}
            st.rerun()

        

    def do_review_dialog(
            header="Editorial Review)", 
            initial_contents=["",""],
            titles=["article","critique"], 
            link_text=None, 
            link_url=None, 
            #radio_labels=[],
            instruction_text="You can edit either the article or the critique.\n Clear the critique to use the article as displayed. ",
            ):
        st.title(header)
        
        # Instructions (if any)
        if instruction_text:
            st.write(instruction_text)
        text_boxes = []
        for content, title in zip(initial_contents, titles):
            st.subheader(title)
            text_input = st.text_area("", value=content, height=300 if titles.index(title) == 0 else 150)
            text_boxes.append(text_input)
        
        if "url" in article:
            link_text = "Click here to open source document in browser."
            link_url = article["url"]
            st.markdown(f"[{link_text}]({link_url})", unsafe_allow_html=True)
            
        if "transcript" in article:
            link_text = "Click here to open source document in browser."
            link_url = article["transcript"]
            st.markdown(f"[{link_text}]({link_url})", unsafe_allow_html=True)

        # OK Button
        if st.button('OK'):
            # Perform actions based on the form submission here
            # For example, print or store the contents of text_boxes

            st.session_state["newvalues"]={"body":text_boxes[0],"critique":text_boxes[1],"button":"OK"}
            text_boxes=""

        
        
    #print(form_number,article)
    if form_number==0:
        if "origin" in article: #if initial dialog happened
            if article["origin"]=="s3": #if file passed in
                set_s3()
            elif article["origin"]=="internet":
                st.text_input("Enter the URL of your source document:",key="url",
                                                           on_change=set_value)
            else: #if have to upload file
                st.file_uploader('Choose your source document',
                                      type=['pdf','docx','html','txt'],
                                      accept_multiple_files=False,
                                      help="""
                                      This is the source for the story you want written.
                                      It can be a pdf, docx, html, or text file
                                      """,
                                      on_change=(set_file),
                                      key="input_file"
                                      )
        if not "origin" in article: #if this is initial dialog
            do_first_dialog()
    elif form_number==1:
        do_review_dialog(
            header = article["title"],
            initial_contents=[article["body"],article["critique"]],
            link_text="Click here to open source document in browser.",
            link_url=article.get("url"),
            )

    elif form_number==2:
        formatted_items=[]
        for item in article['significant_items']:
            formatted_item = f"{item['number']}. {item['description']}\n    Explanation: {item['explanation']}\n"
            formatted_items.append(formatted_item)
        formatted_text = "\n".join(formatted_items)
        do_review_dialog(
        header="significant items",
        initial_contents=[formatted_text,""],
        link_text="Click here to open source document in browser.",
        link_url=article.get("url"),
        titles=["proposed significant items","your instructions. Leave blank to proceed with proposed list as is or the list as edited by you." ], 
        instruction_text="""
            You can either edit the proposed list of significant items or give instructions for changing them.
            If you make no changes, the article will be based on the first five items. The first will be the lede
            and the others will get declining space in the article.
            """
    )

        
def rerun():
    st.session_state['dm'] = None
    st.session_state['result']=None
    st.session_state["newvalues"]=None
            

# Initialize session state
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = None
    st.session_state['dm'] = None
    st.session_state['result']=None
    st.session_state["newvalues"]=None

# App title
st.title("Human-In-The-Loop AI Collaboration with Reflection Agent")
if st.session_state['test']:
    sidebar_message=f"test version only {st.session_state['version']}"
else:
    sidebar_message="""
### What it's all about:

    This application demonstrates
    how artificial intelligence
    agents and a human (you) can
    collaborate on a task.
    
    Today's task is to write a news
    article about a meeting for 
    which a text transcript or 
    minutes are available.
    
    You point to that source;
    the writer agent drafts;
    the critique agent critiques;
    you can edit either the draft or
    the critique. This repeats until
    you are satisfied with a draft.
    v0.0.5
"""
with st.sidebar:

    st.markdown(sidebar_message)

# Sidebar for API key input

if not st.session_state.api_key:
    #with st.sidebar:
    api_key=st.text_input("Enter your ChatGPT API key (Tier 1 or higher account) to get started:", type="password")
    st.markdown("You can also use the custom GPT version free without an API key or a paid subscription by clicking [here](https://chatgpt.com/g/g-roNR24Ty6-collaborative-meeting-reporter).",
                unsafe_allow_html=True)
    if api_key:
        st.session_state['api_key'] =api_key
        st.rerun()
        
if not st.session_state['test']:
    with st.sidebar:
        st.markdown("[custom GPT Version](https://chatgpt.com/g/g-roNR24Ty6-collaborative-meeting-reporter)", unsafe_allow_html=True)
        st.markdown("[feature requests](https://github.com/tevslin/meeting-reporter/discussions)", unsafe_allow_html=True)
        st.markdown("[bug reports](https://github.com/tevslin/meeting-reporter/issues)", unsafe_allow_html=True)
        st.markdown("[source code](https://github.com/tevslin/meeting-reporter)", unsafe_allow_html=True)
        st.markdown("[blog post](https://blog.tomevslin.com/2024/04/human-in-the-loop-artificial-intelligence.html)", unsafe_allow_html=True)    

if st.session_state['api_key'] and st.session_state["dm"] is None:
    os.environ['OPENAI_API_KEY'] = st.session_state['api_key']
    st.session_state['dm'] = mm_agent.StateMachine()
    st.session_state["result"]=st.session_state['dm'].start()
    


if st.session_state["result"]:
    print("have result")
    #st.session_state["newvalues"]
    #if "quit" not in st.session_state['result']:
    if st.session_state["newvalues"] is None:
        process_form(st.session_state['result']["form"],st.session_state['result'])
    if st.session_state["newvalues"] and "next" in st.session_state.newvalues:
        process_form(st.session_state['result']["form"],st.session_state.newvalues)
    if st.session_state["newvalues"] and not "next" in st.session_state.newvalues:
        #if len(st.session_state["newvalues"]["url"])>0:
            print("*********")
            #st.session_state["newvalues"]
            with st.spinner("Please wait... Bots at work"):
                st.session_state["result"]=st.session_state['dm'].resume(st.session_state["newvalues"])
            st.session_state["newvalues"]=None
            st.rerun()
    if "quit" in st.session_state["result"]:
        save_file_dialog(st.session_state['result']['formatted'],st.session_state['result']['output_name'])
        st.button("Run with new document",key="rerun",on_click=rerun)
        st.components.v1.html(st.session_state['result']['formatted'], height=800,scrolling=True)       
        with st.sidebar:
            st.button("Run with new document",key="rerun1",on_click=rerun)
        
            


    


