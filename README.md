# LLMs playground

Just some scripts to play around with LLMs

### Searxng

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
