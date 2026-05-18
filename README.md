# LLMs playground

Just some scripts to play around with LLMs

## Forgetful Chat

This is a streaming chat without any memory. Since the LLM response is streamed to the HTMX frontend interface, it creates a fast and lively conversation with the LLM.

## Simple Agent

This is a non-streaming chat that has an LLM with read_file tool access. Therefore, it requires an LLM that knows how to call tools. It is helpful if you want to send a local file to the LLM and ask the LLM to either summarize or ask a question about the file contents.

## RAG Agent

This is a non-streaming chat that has an LLM and a Vector database that sends text relevant to the user's question to the LLM.

## Researcher (WIP)

This is a non-streaming agent that is supposed to research on the given topic by searching the web and creating a comprehensive report. Unfortunately at the moment it is not working.

## RAG Chat (TBD)

This is a streaming agent with a chat frontend based on React. The goal is to be able to see the files loaded into the Vector database so that the user knows what documents are loaded so far and when.
It should combine ideas from "Forgetful Chat" and "RAG Agent".

## Searxng

The searxng folder and the settings.yml file are required to run the searxng docker container.
It is configured as a tool for the LLM to search the web.

The docker command to run searxng in port 8081 is as follows.

```
 docker run -p 8081:8080 -v /home/anthony/sandbox/agentic_zero/searxng:/mnt/searxng --rm -e SEARXNG_SETTINGS_PATH=/mnt/searxng/settings.yml searxng/searxng
```

Test the search using a curl command as follows.

```
 curl -H 'X-Forwarded-For: 192.168.1.166' 'http://localhost:8081/search?q=What-is-the-current-status-of-local-inference-speed-records-for-405B-class-models-as-of-December-2025?&format=json' | jq '.'
```
