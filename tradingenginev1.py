'''
General idea:
Create one marketholder instance: Singleton
Put all poly and kalshi market Ids that I find into 2 lists, and have websockets monitor them,
updating the order books as it goes.
When a price is updated, check opposing market, do spread math, and execute trade at min size between sides
Currently, do not have any logic for redeeming/selling before event closes. Just sit and wait and figure out after
'''