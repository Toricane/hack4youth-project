# TimeCraft

Effortlessly manage your events and never miss a moment. Connect your Google Calendar and let TimeCraft do the rest.

[![Devpost](https://img.shields.io/badge/Devpost-View_Project-blue?style=for-the-badge&logo=devpost&logoColor=white)](https://devpost.com/software/timecraft-wgcb0u)

## Demo video

[![TimeCraft Demo - Hack For Youth Hackathon Winner](https://img.youtube.com/vi/1JSBGzftZSQ/0.jpg)](https://www.youtube.com/watch?v=1JSBGzftZSQ)

## Inspiration

I was inspired by the recent advancements in the applications of large language models in different areas. I enjoy integrating LLMs with APIs and making them useful other than being just a chatbot.

I face this problem where I have trouble prioritizing things and scheduling events into my calendar. I think it would be awesome if I could just talk to an AI and it can schedule them for me and help me manage my time.

## What it does

TimeCraft connects to your Google Calendar account and schedules events into that account so you stay accountable. It shows your current and upcoming Google Calendar events, and has a chat interface which is connected to an AI. This AI can have conversations with you and modify the events in the account through the Google Calendar API. It helps the user to think through what they have to do, suggests when they could do it, and makes it easier for the user to know what they need to do and when.

## How I built it

I built a Flask website, which has the ability to authenticate the user with the Google Calendar API. I used a lot of HTML, CSS, and JS to design this website and make it look good and functional. The LLM is from Groq, specifically the llama 3.2 90b model, which is used through Groq's API in Python. When the LLM would request to complete an action, it would be parsed and the appropriate function would be called.

## Challenges I ran into

It was difficult to get the Google Calendar-style view on the website. It took a lot of styling and code to make it work.

It was difficult to make the AI understand the system prompt and only provide JSON responses. I found out about the JSON mode, which I used near the end, which resolved the issue.

## Accomplishments that I'm proud of

I'm proud of the fact that I completed so much of the project in 6 hours without any teammates. I probably should have worked together with someone, but did not find a partner, so I decided to work on this project alone.

## What I learned

I learned how difficult it is to get the AI to listen to your instructions, but once you get it working, it works like magic.

## What's next for TimeCraft

Adding voice support would be beneficial, so users can just speak into the AI instead of typing.

## Built with

Python, Flask, HTML, CSS, JS, Groq, Google Calendar API
