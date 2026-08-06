# Intermediate Pack - Improve your Alpha [2/2]

Official URL: https://platform.worldquantbrain.com/learn/documentation/discover-brain/intermediate-pack-part-2
API Source: https://api.worldquantbrain.com/tutorial-pages/intermediate-pack-part-2
Captured: 2026-08-06
Official source: WorldQuant BRAIN Learn Documentation API
Capture method: official_api
Section: Discover BRAIN
Last modified: 2026-08-04T08:56:03.831826-04:00

## Metadata
```json
{
  "id": "intermediate-pack-part-2",
  "tutorial": "discover-brain",
  "tutorial_title": "Discover BRAIN",
  "title": "Intermediate Pack - Improve your Alpha [2/2]",
  "url": "https://platform.worldquantbrain.com/learn/documentation/discover-brain/intermediate-pack-part-2",
  "lastModified": "2026-08-04T08:56:03.831826-04:00",
  "duration": "PT5M",
  "api_source": "https://api.worldquantbrain.com/tutorial-pages/intermediate-pack-part-2",
  "capture_source": "official_api"
}
```

## Content

### Heading

```json
{
  "level": "1",
  "content": "Use Different Operators"
}
```

Remember the cross-sectional operators and time-series operators from the [Starter pack]? You can use them here. Secondly, you can try out different data fields. We recommend exploring the price volume dataset, model dataset and fundamental dataset. Lastly, you can tinker with different simulation settings. These tips should help improve the performance of your second Alpha.

**Divide (/)**

We can divide data fields with other data fields.

Imagine market data being a matrix, with each row representing one date and each column representing one stock. For example, the matrix for close price data of stocks in universe US TOP3000 would look like this:

### Image
- **title**: pic3.png
- **width**: 771
- **height**: 152
- **fileSize**: 39951
- **url**: https://api.worldquantbrain.com/content/images/h-3CeG5_321qVW2-TWKmHiGkOlA=/241/original/pic3.png

And the matrix for open data of above stocks would look like this:

### Image
- **title**: pic4.png
- **width**: 771
- **height**: 152
- **fileSize**: 39898
- **url**: https://api.worldquantbrain.com/content/images/thh4Mz_5X8NJBn6Fwq7z-VjwzNU=/242/original/pic4.png

Say you enter an Alpha expression like ***close/open*** in the Simulate page found in the Alphas dropdown tab. When you click Simulate, BRAIN will evaluate the Alpha expression against the matrix of market data for each date and each stock.

**Rank(x)**

Description: the Rank operator ranks the value of the input data x for the given stock among all instruments, and returns float numbers equally distributed between 0.0 and 1.0

Alpha expression: ***rank(sales/assets)***. If company B has a higher asset turnover ratio (sales/assets) than company A, stock B may outperform stock A. The rank operator helps to limit the extreme values of that ratio.

For example:

### Image
- **title**: pic5.png
- **width**: 771
- **height**: 84
- **fileSize**: 15942
- **url**: https://api.worldquantbrain.com/content/images/PFvnrqwAS5ha7nM8rndvRYHMdFw=/222/original/pic5.png

The numbers imply that if you have $126, you must use $100 to go long stock E (~80% of your total capital). So, your strategy would depend crucially on how the last stock performs. But, isn’t that too risky? Applying the rank function to the alpha expression ***rank(sales/assets)***, you get:

### Image
- **title**: pic18.png
- **width**: 771
- **height**: 84
- **fileSize**: 18443
- **url**: https://api.worldquantbrain.com/content/images/CwVphPBlwyn6w1VAaky3SAJi3KE=/223/original/pic18.png

This time you see that the stock with the largest weight occupies only 40% of your portfolio.

**Ts_rank & Ts_delta Operator**

### Image
- **title**: pic6.png
- **width**: 771
- **height**: 368
- **fileSize**: 181983
- **url**: https://api.worldquantbrain.com/content/images/vCArXwyLJ92Bbx-Z9QtBtvNaKtg=/224/original/pic6.png

Visual Illustration of Ts_rank Operator:

### Image
- **title**: pic7.png
- **width**: 771
- **height**: 502
- **fileSize**: 96245
- **url**: https://api.worldquantbrain.com/content/images/MKlUvYAb5xc9asT1I-8An8_s1lc=/225/original/pic7.png

### Heading

```json
{
  "level": "1",
  "content": "Change Simulation Settings"
}
```

In your first Alpha simulation, you left the simulation settings on default. Changing certain simulation settings may help you improve your Alpha results. We will go through Region, Universe, Neutralization, Decay and Truncation. The other settings will be covered in a later guide.

### Image
- **title**: pic8.png
- **width**: 771
- **height**: 453
- **fileSize**: 57056
- **url**: https://api.worldquantbrain.com/content/images/jA0qlUmgeqa5eDHv0Ko8BcLux1U=/226/original/pic8.png

**Region**

Region refers to the market in which the Alpha will simulate trades, for example, the U.S. equity market or Chinese equity market.

**Universe**

Universe is a set of trading instruments ranked by their liquidity. For example, “US: TOP3000” represents the top 3,000 most liquid stocks in the U.S. market.

**Decay**

Decay is used for averaging the Alpha signal within a specified time window. The settings perform linear decay on the Alpha. Tip: Decay can be used to reduce turnover, but decay values that are too large will attenuate the signal.

### Image
- **title**: pic9 (1).png
- **width**: 677
- **height**: 48
- **fileSize**: 5531
- **url**: https://api.worldquantbrain.com/content/images/ff21Of6zxcu0dU8alDvNTs1EZdk=/217/original/pic9_1.png

**Truncation**

Truncation sets the maximum weight for each stock in the overall portfolio. It aims to guard against excessive exposure to movements in individual stocks. The recommended setting is between 0.05 and 0.1 (entailing 5-10%).

**Neutralization**

Market risks and industry specific risks are prevalent risks within equities. However, these risks can be reduced by creating long-short neutral portfolios using a concept called neutralization. After neutralizing the portfolios to market or industry specific groups, no net position is taken with respect to that group, i.e. allotting the same amount of dollars in long (buying) and short (selling) positions. That way, you are less exposed to risk, whether the entire market goes up or down.

When Neutralization = “Market/Industry/Sub-industry” it does the following operation: *Alpha = Alpha – mean(Alpha)* where Alpha is the vector of weights.

### Image
- **title**: pic10.png
- **width**: 771
- **height**: 105
- **fileSize**: 21736
- **url**: https://api.worldquantbrain.com/content/images/LmcQ3-48mp3Nn6GiJEukthB6LZg=/227/original/pic10.png

If the hypothetical book size is 20 million, we would end up investing $10 million in long positions and $10 million in short positions. Thus, no net position is taken with respect to the market. In other words, the long exposure cancels out the short exposure completely, making this hypothetical strategy market neutral.

The three different neutralization methods determine which groups are used for neutralizing Alpha values. The correct choice of neutralization depends on the logic or formula used by the Alpha. The results should indicate which neutralization will be most effective.
