# WorldQuant Challenge

Source: https://platform.worldquantbrain.com/learn/documentation/discover-brain/challenge-help
API Source: https://api.worldquantbrain.com/tutorial-pages/challenge-help
Captured: 2026-08-03
Official source: WorldQuant BRAIN Learn Documentation API
Section: Discover BRAIN
Last modified: 2025-03-12T05:07:12.194953-04:00

## Metadata
```json
{
  "id": "challenge-help",
  "tutorial": "discover-brain",
  "tutorial_title": "Discover BRAIN",
  "title": "WorldQuant Challenge",
  "url": "https://platform.worldquantbrain.com/learn/documentation/discover-brain/challenge-help",
  "lastModified": "2025-03-12T05:07:12.194953-04:00",
  "duration": "PT3M",
  "api_source": "https://api.worldquantbrain.com/tutorial-pages/challenge-help"
}
```

## Content

## Overview

The WorldQuant Challenge is a perpetual, online, solo competition. Users can submit Alphas to improve their scores and ranking.
Individuals who score 10,000 points may be eligible to receive an invitation for the research consultant opportunity, subject to other criteria(e.g. if they are residents in countries where the BRAIN consultant program is offered). Users who make it to Gold and Silver levels will have access to special training sessions and videos through the Events page.
New users are automatically enrolled into the challenge. The Leaderboard ranks all eligible users and can be filtered by country, university and/or city.

## Scoring criteria

### Summary

Your score is based on the quantity and quality (performance in the 5 year in-sample period) of Alphas that you submit on the platform
Your score also depends on quantity and quality of Alphas submitted by other users that day
Score is calculated per day (EST timezone), and not per Alpha
Highest daily score you can achieve is 2,000. Typically, this involves submitting 1 to 2 Alphas a day
There are no negative points. Your score cannot decrease
Scores refresh once every day at 3 AM EST
Participants with the same score will have the same rank
You can reach three levels in WorldQuant Challenge:Bronze (score > 1,000)
Silver (score > 5,000)
Gold (score > 10,000)

### Details

Each day, all Alphas submitted by a user accumulated and two factors are calculated:
Quantity Factor: Larger the number of Alphas you submit during a day. Larger the factor, higher your score
Quality factor: Quality factor is calculated as an average of the quality factor of all Alphas submitted during the day. Larger the factor, higher your score. It depends on the following settings and results in the in-sample period:
Universe (smaller universes get more score)
SelfCorrelation (the lesser the better)
Fitness (the higher the better)
Delay (D1 Alphas contribute more to the score than D0 Alphas)
Both factors are then normalized across all the users who submitted at least one Alpha on that particular day. Your final daily score is then function of normalized Quantity and Quality Factors. The daily score is capped at 2,000 points.
