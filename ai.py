from discord.ext.commands import Bot
import discord
import requests
import datetime as dt
from bs4 import BeautifulSoup
import wolframalpha
import wikipedia
from googlesearch import search
import re
import subprocess

BOT_PREFIX = ("?")

with open ('./token') as tf:
    TOKEN = tf.read().strip()

with open('./wolfram_app_id') as wai:
    appID = wai.read().strip()

# client/startup
client = Bot(command_prefix=BOT_PREFIX)
int_client = wolframalpha.Client(appID)

# clientside stuff. tells what the bot's up to behind the scenes.
# This lists the bot's username, client ID, current time, current servers in terminal
@client.event
async def on_ready():
    await client.wait_until_ready()
    print("Logging in...")
    print("Username: " + str(client.user.name))
    print("Client ID: " + str(client.user.id))
    print(dt.datetime.now().time())
    print("Current Servers:")
    for server in client.guilds:
        print(server.name)
    print("Starting...")
    print("Bot online!")
    print("----------")

@client.command()
async def greet(ctx):
    await ctx.send("Hello!")
    await ctx.invoke(info)

# dev tool | command shutdown: shuts down the bot from server
# MUST HAVE ROLE "BOTMASTER" TO USE
@client.command(aliases=["dev_sd"])
@discord.ext.commands.has_role('Botmaster')
async def shutdown(ctx):
    await ctx.send("Shutting down. Bye!")
    await client.logout()
    await client.close()

# dev tool | command status: set game status of bot
# MUST HAVE ROLE "BOTMASTER" TO USE
@client.command()
@discord.ext.commands.has_role('Botmaster')
async def status(ctx):
    await client.change_presence(activity=discord.Game(name=ctx.message.content[7:]))

# command pythonhelp: searches the python docs for an article
@client.command(aliases=["pyhelp","ph"])
async def pythonhelp(ctx):
    messagetext = ctx.message.content
    split = messagetext.split(' ')
    if len(split) > 1:
        messagetext = split[1]
        # search the site
        # the python docs site uses some javascript stuff to dynamically load search results
        # as a result BeautifulSoup threw a royal fit and I can't pin down any appropriate tags
        await ctx.send(f"The top result for that search is: https://docs.python.org/3/library/{messagetext}.html")


# command cpphelp: searches cppreference for an article
@client.command(aliases=["cref", "ch"])
async def cpphelp(ctx):
    messagetext = ctx.message.content
    split = messagetext.split(' ')
    if len(split) > 1:
        messagetext = split[1]
        # create the search query
        cpp_search = f'http://en.cppreference.com/mwiki/index.php?title=Special%3ASearch&search={messagetext}'
        # fetch the site
        r = requests.get(cpp_search)
        # parse the site through BeautifulSoup
        soup = BeautifulSoup(r.content, 'html5lib')
        # Narrow down to the div class mw-search-result-heading, grab the first <a href="">
        search_result = soup.find('div', attrs={'class' : 'mw-search-result-heading'}).find('a').get('href')
        # Append the <a href=""> to the appropriate URL
        cpp_result = f'https://en.cppreference.com/{search_result}'
        # Return the query
        await ctx.send(f"The top result for that search is: {cpp_result}")

# command stackoverflowhelp: searches stackoverflow for help
# This function is more or less the same as the cppreference one
# see that one's documentation for this one
@client.command(aliases=["so"])
async def stackoverflowhelp(ctx):
    messagetext = ctx.message.content
    split = messagetext.split(' ')
    if len(split) > 1:
        messagetext = split[1]
        so_search = f'https://stackoverflow.com/questions/tagged/{messagetext}?sort=votes&pageSize=15'
        site = requests.get(so_search)
        content = BeautifulSoup(site.content, 'html.parser')
        questions = content.select('.question-summary')
        links = []
        for question in questions:
            url = question.select( '.question-hyperlink')[0].get('href')
            links.append(url)
        #links = link(map(lambda question: question.select( '.question-hyperlink'), questions))
        embed = discord.Embed(title = f"Top five results for {messagetext}:", color=0x00cc99)
        for i in range(0, 5):
            embed.add_field(name=i, value=f'https://stackoverflow.com{links[i]}')
        await ctx.send(embed=embed)

# The Wikipedia and Wolfram|Alpha commands are based off of this:
# https://medium.com/@salisuwy/build-an-ai-assistant-with-wolfram-alpha-and-wikipedia-in-python-d9bc8ac838fe
# command wiki: searches wikipedia
@client.command()
async def wiki(ctx, a):
    # grab the query
    querytext = str(a)
    # run the query
    wiki_search_result = wikipedia.search(querytext)
    # if there is no result:
    if not wiki_search_result:
        await ctx.send("I apologize, but there does not seem to be any information regarding that.")
        return
    # search page try block
    try:
        page = wikipedia.page(wiki_search_result[0])
    except wikipedia.DisambiguationError as err:
        # grab first item on list
        page = wikipedia.page(err.options[0])
    # encode response utf-8
    wikiTitle = str(page.title.encode('utf-8'))
    wikiSummary = str(page.summary.encode('utf-8'))
    # spit the result out prettily
    embed = discord.Embed(title = wikiTitle[1:].strip('\''), color=0x00cc99)
    embed.add_field(name="Summary:", value=wikiSummary[1:]) if len(wikiSummary) < 1020 else embed.add_field(name="Summary:", value=wikiSummary[1:1020] + "...")
    embed.add_field(name="Full Article:", value=f"https://en.wikipedia.org/wiki/{a}")
    await ctx.send(embed=embed)

# comand wolfram: searches Wolfram|Alpha.
@client.command(aliases=['wolf', 'wa'])
async def wolfram(ctx, a):
    res = int_client.query(a)
    # in the event that Wolfram cannot resolve the question:
    if res['@success'] == 'false':
        await ctx.send("I apologize, but I cannot resolve this query.")
    # otherwise, Wolfram was able to figure it out.
    else:
        result = ''
        # pod[0] is the question
        pod0 = res['pod'][0]
        # pod[1] is the answer with highest confidence
        pod1 = res['pod'][1]
        # check if pod1 has primary=true or title=result|definition
        if(('definition' in pod1['@title'].lower()) or ('result' in pod1['@title'].lower()) or (pod1.get('@primary','false') == 'true')):
            # grab result
            result = resolveListOrDict(pod1['subpod'])
            # spit the result out prettily
            embed = discord.Embed(title = resolveListOrDict(pod0['subpod']), color=0x00cc99)
            embed.add_field(name="Wolfram Says: ", value=result)
            await ctx.send(embed=embed)
        # otherwise we extract Wolfram's question interpretation and throw it to wikipedia
        else:
            question = resolveListOrDict(pod0['subpod'])
            question = removeBrackets(question)
            # in order to call a command function, you have to await/invoke it
            await ctx.invoke(wiki, question)

# supplementary functions to above
def removeBrackets(variable):
    return variable.split('(')[0]
def resolveListOrDict(variable):
    if isinstance(variable, list):
        return variable[0]['plaintext']
    else:
        return variable['plaintext']

# command google runs google search.
@client.command(aliases=['google', 'g'])
async def google_search(ctx, a):
    query = a
    embed = discord.Embed(title=f"Search results for \"{query}\":", color=0x00cc99)
    for j in search(query, tld="co.in", num=5, stop=1, pause=2):
        embed.add_field(name=f"Result: ", value=j, inline=False)
    await ctx.send(embed=embed)

@client.command()
async def call_gcc(ctx):
    messagetext = ctx.message.content
    split = messagetext.replace('?call_gcc ```', '')
    if len(split) > 1:
        codesnippet = split.replace('```', '')
        print("Creating C++ file...")
        f = open("usercode.cpp", "w+")
        f.write(codesnippet)
        f.close()
        cmd = "usercode.cpp"
        print("Calling GCC for assembly!")
        subprocess.call(["gcc", "-S", "./usercode.cpp"])


# command info: tells you about this bot
@client.command()
async def info(ctx):
    embed = discord.Embed(title="An Aggravating Intelligence", description="An Aggravating Intelligence", color=0x00cc99)
    embed.add_field(name="Version", value="1.0")
    embed.add_field(name="Author", value="Esherymack | Madison Tibbett")
    embed.add_field(name="Server count", value=f"{len(client.guilds)}")
    await ctx.send(embed=embed)

# overwrite the help command with something pretty
client.remove_command('help')
@client.command()
async def help(ctx):
    embed = discord.Embed(title="Aggravating Intelligence", description = "Accepted intonations are:", color=0x00cc99)
    embed.add_field(name="?shutdown", value="Shuts the bot down. Must have requisite role \"Botmaster.\"", inline=False)
    embed.add_field(name="?status", value="Sets the in-game status of the bot. Must have requisite role \"Botmaster.\"", inline=False)
    embed.add_field(name="?info", value="Gives info regarding this servitor's development.", inline=False)
    embed.add_field(name="?help", value="Gives this message.", inline=False)
    embed.add_field(name="?greet", value="Same function as info, with the addition of a hello.", inline=False)
    embed.add_field(name="?pythonhelp | ?pyhelp | ?ph", value="Fetches an article from the Python 3 docs.", inline=False)
    embed.add_field(name="?cpphelp", value="Fetches an article from the cppreference website.", inline=False)
    embed.add_field(name="?stackoverflowhelp | ?so", value="Fetches the top five most highly rated questions for a specific query.", inline=False)
    embed.add_field(name="?wiki", value="Searches Wikipedia for an article.", inline=False)
    embed.add_field(name="?wolfram | ?wolf", value="Queries Wolfram|Alpha.", inline=False)
    embed.add_field(name="?google", value="Searches google for a query; returns a number of results.", inline=False)
    await ctx.send(embed=embed)

client.loop.create_task(on_ready())

client.run(TOKEN)
