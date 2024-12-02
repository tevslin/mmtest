from datetime import datetime
import json5 as json
import pickle
from langgraph.graph import Graph

from langchain.adapters.openai import convert_openai_messages
from langchain_openai import ChatOpenAI
from mytools import markdown_to_html,generate_html_from_html_data,find_direct_quotes,find_missing_strings,load_binary_file_from_url

MODEL='chatgpt-4o-latest'
VERSION="4"

writing_instructions="""
Using the transcript or minutes of a meeting provided by the user as your primary source, 
craft a compelling news report of {str(article['words'])} words which captures the essence and impact of the discussed topics. 
A news report of a meeting is a concise, objective, and informative summary that highlights the key discussions, decisions, and outcomes of a gathering, such as a local government meeting. It goes beyond a simple meeting summary by focusing on the most newsworthy aspects and explaining their relevance and potential impact on the community. A well-crafted news report should engage readers, provide essential context, and adhere to journalistic standards of accuracy, fairness, and clarity.  

Using the transcript or minutes from the recent meeting as your primary source, craft a compelling news report of {str(article['words'])} that captures the essence and impact of the discussed topics. The news report should not merely summarize the meeting but instead focus on the broader implications and reactions to the decisions made. Here are the specific elements to include in your report:
1.	Headline: Create an attention-grabbing headline that succinctly conveys the main point or outcome of the meeting. Think about what makes this news significant and why it matters to the public.
2.	Lead Paragraph: Open your report with a lead paragraph that summarizes the key news piece from the meeting, focusing on answering who, what, when, where, and why. This should capture the most newsworthy aspect and draw the reader in.
3.	Context and Background: Provide context for the discussions, including any background information necessary for understanding why the meeting was held and the issues at stake. Mention any previous events, controversies, or decisions that are relevant to the current discussions.
4.	Key Outcomes and Decisions: Detail the major outcomes and decisions made during the meeting. Explain how these decisions were reached and their potential impact on various stakeholders or the general public.
5.	Use quotes from the transcript in qoutation marks to give color and reaction. There should be at least one such quote
    for the first and second most significant items.
6.	Implications: Analyze the broader implications of the meeting’s outcomes. How will these decisions affect the future of the organization, community, or field? What are the potential benefits or consequences?
7.	Follow-up Actions: Mention any planned follow-up actions or events that have been scheduled in response to the meeting's outcomes. This could include further meetings, implementation plans, or protests.
8.	Visuals and Other Media: Suggest any visuals, charts, or other media that could enhance the report. Describe these elements and how they contribute to the story.
9.	Closing: Wrap up the report by summarizing the main points and perhaps posing a question or highlighting areas of uncertainty that could affect future developments.

Special instructions for quotes:
    text in quotes will be used to link the words to video clips so must be verbatim from the transcript
    quotes from the transcripts preserve any errors and informal language.
    They must be ABSOLUTELY word for word and letter for letter verbatim from the transcript. 
    Do not invent them. alter them, correct or abridge them in any way, even if they contain obvious transcription errors.
    People don't speak perfectly and the transcription may be inaccurate but you must NOT correct errors when extracting.
    for example:
        Don't change "30" to "thirty" or vice versa. Always use whatver form of a number is in the transcript.
        Don't change "gonna" to "going to" "have to" or "must". Preserve all colloquilisms.
        Don't remove repeated words or phrases.For example don't remove the duplicate phrase"the bridge" from 
        "it'll be expensive to fix the bridge, the bridge, even if we do it ouselves".
    If a quote contains a misspelled proper name, don't correct it and don't use it. find another extract.
    You may follow an quote which contains what seem like errors with "(sic)" to indicate that this is what was said rather
    than what may have been meant.
    
    Do not escape quotation marks with backslashes.
        
    If it is necessary to paraphrase a quote, make it an indirect quote  'speaker 0 said that...' rather than a literal quote
    'speaker 0 said "..."'. in that case put the verbatim text from the transcript which has been paraphrased in square brackets following the indirect quote.
    
Ensure that your report is engaging, factually accurate, and provides a comprehensive view of the meeting's importance and impact. This approach will help in making the news report informative, insightful, and relevant to the audience.
"""
def check_quotes(article,transcript,prompt):
    # routine to make sure prompts have accurate source
    quotes=find_direct_quotes(article)
    if not quotes:
        print ('no quotes in article')
        return article
    missing_quotes=find_missing_strings(quotes,transcript)
    if not missing_quotes:
        print("all quotes found")
        return article
    display='\n'.join(missing_quotes)
    print(f"quotes missing ain draft article:\n{display}")
    prompt.append({
        "role":"user",
        "content":f"""
        the following quotes from body of the story you wrote were not found verbatim in the source transcript.
        replace them with quote which are verbatim word for word and letter for letter from the transcript
        and return only the amended story
        {display}
        """
        })
    lc_messages = convert_openai_messages(prompt)
    article = ChatOpenAI(model=MODEL, max_retries=1, temperature=0).invoke(lc_messages).content
    quotes=find_direct_quotes(article)   
    if not quotes:
        print ('no quotes in revised article')
        return article
    missing_quotes=find_missing_strings(quotes,transcript)
    if not missing_quotes:
        print("all quotes found in revised article")
        return article
    display='\n'.join(missing_quotes)
    print(f"quotes missing after first pass:\n{display}")
    prompt.append({
        "role":"assistant",
        "content":article})
    prompt.append({
        "role":"user",
        "content":f"""
        the following quotes from body of the story you wrote were not found verbatim in the source transcript.
        They are instead paraphrases.
        Turn them into indirect quotes with NO quotation marks and follow each with the verbatim text from the transcript
        which was paraphrased in square brackets and double quotation marks inside the square brackets. We are
        looking for errors and the text in quotation marks will be used to sync with the transcript and must be absolutely
        verbatim from the transcript including repeated words and other speaking and trancription errors.
        {display}
        """
        })
    lc_messages = convert_openai_messages(prompt)
    article = ChatOpenAI(model=MODEL, max_retries=1, temperature=0).invoke(lc_messages).content
    quotes=find_direct_quotes(article)
    if not quotes:
        print ('no quotes in second revised article')
        return article
    missing_quotes=find_missing_strings(quotes,transcript)
    if not missing_quotes:
        print("all quotes found in second revised article")
        return article
    display='\n'.join(missing_quotes)
    print(f'article contains unmatched quotes:\n{display}')
    return f"""WARNING: the following quotes do not exactly match the transcript:\n
{display}\n
{article}
        """

class WriterAgent:

    def writer(self, article):
        
        sample_json = f"""
            {{
              "title": title of the article,
              "date": meeting date,
              "body": The body of the article as a text of {str(article['words'])} words divided into paragraphs separated by newline characters and formatted as markdown.
              "information_suggested": information not in the transcript or minutes which would be helpful to a more complete story,
              "summary": 2 sentences summary of the article
            }}
            """

        prompt = [{
            "role": "system",
            "content": f"""
{writing_instructions}
Return nothing but JSON in the following format:
        {sample_json}
    """

        }, {
            "role": "user",
            "content": f"""Here is the source document describing the meeting:
               {article['source']}
            
            Below is a list in descending order of significance of issues covered in the meeting.
            The first item should be the lede for the story and have approximately 1/3 of the story devoted to it.
            The second item should have half as much space, the third item even less. The remaining items get just a mention.
            {article['significant_items']}
            """
            

        }]

        lc_messages = convert_openai_messages(prompt)
        optional_params = {
            "response_format": {"type": "json_object"}
        }

        response = ChatOpenAI(model=MODEL, max_retries=1, temperature=.5,model_kwargs=optional_params).invoke(lc_messages).content
        response_dict=json.loads(response)
        prompt.append({
            "role": "assistant",
            "content": response  # Add the AI's response content
        })
        response_dict['body']=check_quotes(response_dict['body'],article['source'],prompt)
        print ("writer",VERSION,response_dict["information_suggested"],response_dict["summary"])
        return response_dict

    def revise(self, article: dict):
        sample_revise_json = """
            {
                "body": The body of the article,,
                "message": "message to the critique"
            }
            """
        prompt = [{
            "role": "system",
            "content": f"""
            You are a newspaper editor. Your task is to edit an article which the user will supply you
            in accordance with a critique which the use will also suppy. You must adhere to these instructions:
                {writing_instructions}
            return json format of the rewritten article {sample_revise_json}
            the message item in the json is for any message you have about instructions you were not able to follow
            """
            
        }, {
            "role": "user",
            "content": f"""
            following your system instructions
            rewrite the article below:
                {str(article['source'])}
            as instructed in the critique below:
                {article['critique']}
            """
        }]

        lc_messages = convert_openai_messages(prompt)
        optional_params = {
            "response_format": {"type": "json_object"}
        }
        article['critique']=""
        response = ChatOpenAI(model=MODEL, max_retries=1, temperature=.5,model_kwargs=optional_params).invoke(lc_messages).content
        response = json.loads(response)
        print(f"For article: {article['title']}")
        print(f"Writer Revision Message: {response['message']}\n")
        return response

    def run(self, article: dict):
        print(f"writer {VERSION} working...,{article.keys()}")
        critique = article.get("critique")
        if critique is not None:
            article.update(self.revise(article))
        else:
            article.update(self.writer( article))
        return article


class CritiqueAgent:

    def critique(self, article: dict):
        #short_article=article.copy()
        #del short_article['source'] #to save tokens
        prompt = [{
            "role": "system",
            "content": """"
            You are a newspaper writing critiquer. Your ask is to provide short feedback on a written "
            article which the user will provide you.
            the article is a news story so should not include editorial comments.
            Be sure that names are given for split votes and for debate.
            The maker of each motion should be named."
            if you think the article is as good as it can be, please return only the word 'None' without the surrounding hash marks.
            Try to find at least one thing to improve in the article""
            """
        }, {
            "role": "user",
            "content": f"""
            Today's date is {datetime.now().strftime('%d/%m/%Y')}.
            The article and the transcript on which it is based are in the text below:
            {str(article)}
            """
                  
        }] 

        lc_messages = convert_openai_messages(prompt)
        response = ChatOpenAI(model="gpt-4o",temperature=1.0, max_retries=1).invoke(lc_messages).content
        if response == 'None':
            return {'critique': None}
        else:
            print(f"For article: {article['title']}")
            print(f"Feedback: {response}\n")
            return {'critique': response, 'message': None}

    def run(self, article: dict):
        print("critiquer working...",article.keys())
        article.update(self.critique(article))
        article["form"]=1
        if "message" in article:
            print('message',article['message'])
        return article


class InputAgent:
       
    def run(self,article:dict):
        from mytools import extract_text, load_text_from_path, load_text_from_url
        
        print ("input agent running...")
        print(article.keys())
        if "transcript" in article:
            the_text=load_text_from_url(article["transcript"])
        elif "url" in article:
            the_text=load_text_from_url(article["url"])
            
        else:
            if "raw" in article: #if already read
                the_text=extract_text(content=article['raw'],content_type=article["file_name"].split('.')[-1])
                del article["raw"]
            else:
                the_text=load_text_from_path(article['file_name'])
        article["source"]=the_text
        return article
            
class OutputAgent:
    def run(self,article:dict):
        #print(f"Title: {article['title']}\nSummary: {article['summary']}\nBody:{article['body']}")
        markdown_article=markdown_to_html(article['body'],title=article['title'],date=article['date'],
                                  smart_transcript=article.get('url'))
        if 'pickle' in article: #if we are supposed to make smartstory
            article["output_name"]="SmartStory.html"
            pickle_data=load_binary_file_from_url(article['pickle'])
            deepgram_return=pickle.loads(pickle_data)
            article['formatted']=generate_html_from_html_data(markdown_article,article['video'],deepgram_return)
        else:
            article["output_name"]="Story.html"
            article['formatted']=markdown_article
        #print (article['formatted'])
        
        article['form']=3 
        article['quit']='yes'      
        return article

class OutlinerAgent:
    name='outliner'
    def run(self,article:dict):
        sample_json="""
        "significant_items":
        [{"number": <item number starting at 1>,
          "description":<brief description of item>,
          "explanation:<brief explanation of item significance>"},
          .....}
        ]
         """
        start_prompt_content = f"""
You are an editor in a newsroom. Using the transcript or minutes of a meeting provided by the user as your sole source, 
create a numbered list of the ten most significant actions or topics in the meeting starting with the most significant.
Significance is determined by factors which include controversy surrounding each item, the amount of discussion about the item, 
and the likely effect of the item. The list should not include items like the meeting opening 
unless there is something very significant about the opening.
"""
        if 'significant_items' in article: 
            revise_prompt_content=f"""
You are an editor in a newsroom. You previously provided this list of significant items 
based on the transcript or meeting description provided by the user:
    {article['significant_items']}
In a message below the user has requested changes to the list which you must now accomplish.
"""

        the_prompts=[
            {"role":"system",
             "content":f"""
             {revise_prompt_content if 'revisons' in article else start_prompt_content}
             Return only JSON in the following format:
            {sample_json}
            """},
            {"role":"user",
            "content":f"""
            This is the source information for the meeting
            {article['source']}.
            {"this is how I'd lke you to revise it:"+ article["critique"] if "critique" in article else ""}
            """ 
             }]

        
        lc_messages = convert_openai_messages(the_prompts)
        optional_params = {
            "response_format": {"type": "json_object"}
        }
        reply = ChatOpenAI(model=MODEL, max_retries=1, temperature=.5,model_kwargs=optional_params).invoke(lc_messages)
        response_dict=json.loads(reply.content)
        article.update(response_dict)
        article["form"]=2
        return(article)
      
      
class HumanReviewAgent:
    def run(self,article:dict):
        print("human review agent running",article.keys())
        if article["button"]=='OK':
            if not article["critique"] or len(article['critique'].strip())==0:
                article["critique"]=None
                #article["quit"]="yes"
        else:
            assert False,"Canceled by editor"
        #print("from user:",article["body"],"\n","from dialog:",result["text1"])
        return article
    
class StartAgent:
    name='start'
    def run(self,dummy):
        print("start agent working")
        return {"form":0,"name":self.name}
          
            
        
class StateMachine:
    def __init__(self,api_key=None):
        import os
        from langgraph.checkpoint.memory import MemorySaver
 
        if api_key:
            os.environ['OPENAI_API_KEY']=api_key
        else:
            from dotenv import load_dotenv
            load_dotenv()
        self.memory=MemorySaver()

        start_agent=StartAgent()
        input_agent=InputAgent()
        writer_agent = WriterAgent()
        critique_agent = CritiqueAgent()
        output_agent=OutputAgent()
        human_review=HumanReviewAgent()
        outliner_agent=OutlinerAgent()

        workflow = Graph()

        workflow.add_node(start_agent.name,start_agent.run)
        workflow.add_node("input",input_agent.run)
        workflow.add_node("outliner",outliner_agent.run)
        workflow.add_node("write", writer_agent.run)
        workflow.add_node("critique", critique_agent.run)
        workflow.add_node("output",output_agent.run)
        workflow.add_node("human_review1",human_review.run)
        workflow.add_node("human_review2",human_review.run)
        

        workflow.add_edge("input","outliner")
        workflow.add_edge("outliner","human_review1")
        workflow.add_conditional_edges(source='human_review1',
                               path=lambda x: "accept" if x['critique'] is None else "revise",
                               path_map={"accept": "write", "revise": "outliner"})
        workflow.add_edge('write', 'critique')
        workflow.add_edge('critique','human_review2')
        workflow.add_edge(start_agent.name,"input")
        workflow.add_conditional_edges(source='human_review2',
                                       path=lambda x: "accept" if x['critique'] is None else "revise",
                                       path_map={"accept": "output", "revise": "write"})
                                       
        
        # set up start and end nodes
        workflow.set_entry_point(start_agent.name)
        workflow.set_finish_point("output")
        
        self.thread={"configurable": {"thread_id": "2"}}
        self.chain=workflow.compile(checkpointer=self.memory,interrupt_after=[start_agent.name,"outliner","critique"])
    def start(self):
        result=self.chain.invoke("",self.thread)
        #print("*",self.chain.get_state(self.thread),"*")
        #print("r",result)
        if result is None:
            values=self.chain.get_state(self.thread).values
            last_state=next(iter(values))
            return values[last_state]
        return result
        
    def resume(self,new_values:dict):
        values=self.chain.get_state(self.thread).values
        #last_state=self.chain.get_state(self.thread).next[0].split(':')[0]
        last_state=next(iter(values))
        #print(self.chain.get_state(self.thread))
        values[last_state].update(new_values)
        self.chain.update_state(self.thread,values[last_state])
        result=self.chain.invoke(None,self.thread,output_keys=last_state)
        #print("r",result)
        if result is None:
            values=self.chain.get_state(self.thread).values
            last_state=next(iter(values))
            return self.chain.get_state(self.thread).values[last_state]
        return result       
      

if __name__ == '__main__': #test code
    
    from mm_tkinter import process_form

       
    sm=StateMachine()
    result =sm.start()
    while True:
        new_values=process_form(result["form"],result)
        if 'quit' in result:
            break
        result=sm.resume (new_values)
    