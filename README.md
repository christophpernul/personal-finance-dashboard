# Personal-Finance Dashboard
Dashboard giving an overview of personal finances. It contains multiple tabs:
1. Overview of monthly expenses
2. Overview of monthly income
3. Overview of monthly ETF savings plan
4. Overview of overall portfolio value
5. Timeseries of portfolio value

The dashboard was built using Python Plotly Dash:[https://dash.plotly.com/]()

## Input data schemata
- finanzübersicht.ods (libreOffice calc)
    - Sheet: 3.2 Portfolio langfristig Transactions
        Columns: 
            "Index": Index for a single savings plans execution (integer, is empty in case of dividend payments)
            "Datum": Date of execution (dd.MM.yyyy)
            "Kurs": Price of stock (xx.xx)
            "Betrag": Amount (€) of investment per execution (xx.xx)
            "Kosten": Costs (ordercost in xx.xx)
            "Anbieter": Brokername
            "Name": Name of stock
            "ISIN": ISIN of stock
            "Art": Type of investment (should be "ETF Sparplan" for savings plan)
            "Kommentar": Should be "monatlich" for savings-plan entry and "Dividende" for a dividend payment
    - Sheet: 3.4 Spekulation Transactions
            not used atm
    - Sheet: 3.3 Income Transactions
            "Datum": Date of income transaction (dd.MM.yyyy)
            "Art": Type of income ("Gehalt")
            "Betrag": amount (xx.xx)
- stock_prices.ods ((libreOffice calc)
        - created with script "update_finance_data.py"
- master_data_stocks.ods (libreOffice calc)
        - created with script "update_finance_data.py"
- bilanz_full.csv
        - Multiple monthly Toshl export files are appended into a single file
            The app assumes, that you use a single category and a single tag for each entry. The tags are later remapped to custom categories, that are more useful.

## 1. Overview of monthly expenses

This tab shows average monthly expenses, as well as a more detailled analysis of all monthly expenses:
- Total monthly expenses over time: Barchart can be filtered on
    - Timeframe: How many months into the past should be displayed?
    - Category: Expenses are categorized (custom definition)
- Barchart for expenses per category in a selected month

![alt text](https://github.com/christophpernul/personal-finance-dashboard/blob/main/documentation/finance_dashboard_expenses.png)

## 2. Overview of monthly income

This tab shows average monthly income as well as a barchart, that can be customized by dropdown filters:
- Timeframe: How many months into the past should be displayed?
- Category: Expenses are categorized (custom definition)

![alt text](https://github.com/christophpernul/personal-finance-dashboard/blob/main/documentation/finance_dashboard_income.png?raw=true)

## 3. Overview of monthly ETF savings plan

This tab shows a list of all ETF's in the monthly savings plan together with some useful informations like
total expense ratio (TER), region and further ETF properties as well as the investment amount for each.

A KPI panel shows average cost and investment per month. Furthermore interesting portfolio statistics, like  
 distribution across regions (diversification), types and replicationmethods are shown as piecharts at the bottom.

![alt text](https://github.com/christophpernul/personal-finance-dashboard/blob/main/documentation/finance_dashboard_monthlyPlan.png?raw=true)

## 4. Overview of overall portfolio value

It is similar to the previous tab, only that it shows the analysis for the overall portfolio and the total most recent
value.

![alt text](https://github.com/christophpernul/personal-finance-dashboard/blob/main/documentation/finance_dashboard_overallPortfolio.png?raw=true)

## 5. Timeseries of portfolio value

The time-series of the overall portfolio value is shown together with the total amount of investment accumulated.
The time-series chart can be filtered for a specific timeframe as well as for certain ETF's only.

![alt text](https://github.com/christophpernul/personal-finance-dashboard/blob/main/documentation/finance_dashboard_portfolioTimeseries.png?raw=true)
