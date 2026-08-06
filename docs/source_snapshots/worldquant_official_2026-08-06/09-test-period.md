# Test Period

Official URL: https://platform.worldquantbrain.com/learn/documentation/create-alphas/test-period
API Source: https://api.worldquantbrain.com/tutorial-pages/test-period
Captured: 2026-08-06
Official source: WorldQuant BRAIN rendered Learn page via Chrome
Capture method: rendered_website
Section: Create Alphas
Last modified: None

## Metadata
```json
{
  "id": "test-period",
  "tutorial": "create-alphas",
  "tutorial_title": "Create Alphas",
  "title": "Test Period",
  "url": "https://platform.worldquantbrain.com/learn/documentation/create-alphas/test-period",
  "lastModified": null,
  "duration": null,
  "api_source": "https://api.worldquantbrain.com/tutorial-pages/test-period",
  "capture_source": "rendered_website"
}
```

## Content

![Settings dropdown](https://api.worldquantbrain.com/content/images/N4MAKvOE4TFpqJzzDk3QI672b6k=/288/original/Settings_dropdown.png)

The Test Period is a feature designed to enhance your Alpha and SuperAlpha testing process. This tool allows you to set a separate test period from your IS period, providing a more flexible approach to testing your research ideas.

Using the Feature:

The Test Period feature is designed to help you avoid overfitting. It allows you to divide your In-Sample (IS) period into a Train and Test period. The Train period can be utilized to develop your Alphas and SuperAlphas, while the Test period is ideal for validating them. An Alpha or SuperAlpha that is developed based on the simulation results of Training Period and performs well in both periods is likely a strong candidate for submission and may have avoided overfitting.

While choosing a Test period does not directly affect the simulation, it influences the statistics and the visualization. The submission tests will run on the entire 5-year period, with the simulation running on the entire 5-year IS. However, if a testing period is chosen, the simulation stats will be divided into two sections: one covering the training period and another for the test period.

Navigating the Feature:

1. Selecting the Test Period: In Simulation Settings, you can define a test period corresponding to the final 0-5 years of the IS period. By default, no test period is set (0 years).
2. Visualizing the Test Period: The Stats Summary defaults to the training period. You can view the stats for the test period by clicking on the “Show test period” button.
3. Identifying the Test Period on Graphs: The lines representing the test period on the graphs are colored orange.
4. Choosing the Stats Summary: You can select between the Stats Summary for the test period or the entire IS period by choosing the “TEST” or “IS” in the Summary section, respectively.
5. Hiding the Test Period: A button “Hide test period” allows you to hide the test period, if desired. Note that an Alpha or SuperAlpha can only be submitted when the Test Period is revealed by clicking on the “Show test period” button.
6. Understanding the Stats: The yearly IS stats are divided between Train and Test periods, represented by blue and orange indicators respectively.

![Test Period Graph and Table.png](https://api.worldquantbrain.com/content/images/asnZoWaMUOts948N-mJgE75To1A=/425/original/Test_Period_Graph_and_Table.png)

A. Orange - test period PnL, Blue - Train period PnL. B. View IS summary by selecting different periods
