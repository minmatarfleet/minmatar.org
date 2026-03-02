
Hello morphite gamers!

Many of you are probably thinking that the [last group on earth is the one that slings dreads at people every single week](https://www.reddit.com/r/Eve/comments/1r3qwgt/aar_200b_dread_brawl_in_dronelands/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button), but here in Minmatar, **industry is serious business**.

When you fight Fraternity over battlefields every single day and feed groups at a rate[ like us](https://zkillboard.com/alliance/99011978/stats/), having a steady supply of reasonably priced ships is a must. Hell, we've only got 180 weekly active characters and are burning through 500 billion ISK in ships **per month**.

Today we'd like to give a peek at how we're optimizing our supply chain, and hopefully give some of our friends in Amarr Empire some ideas on how to bring even more battleships to run away from us in.

# Overview

Minmatar Fleet is an technology first, "fuck paper pushing" kind of alliance. We don't like federated buybacks, federated programs, or things that scream imperialistic space government. That's for Amarr and people who want to burn out.

The best way to fight this is **transparency**. That's why we post all of our [doctrines](https://my.minmatar.org/ships/doctrines/list/). Our entire [market](https://my.minmatar.org/market/).

When all of our information is available to everyone, people can get involved.

So, what do we need to visualize? How do we make it so that people know what to build, how to build it, and what the bottlenecks are?

# Outputs

[https://my.minmatar.org/industry/orders/](https://my.minmatar.org/industry/orders/)

First, you need to see what you... need. If you browse this subreddit a lot, you've probably seen us spam [infographics ](https://www.reddit.com/r/Eve/comments/1gwh0yc/another_year_of_minmil_contracts/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button)around ships and things that we're going through. We've been tracking outputs for years, but not really doing anything with it.

To help this process along, we started storing things as "orders", which fleet commanders and upstart contract seeders typically place. We've learned that people who build want to just build, and they don't typically want to tie up billions of ISK in ships on contract.

From the orders page, we start to visualize all of the things that make up the items we need. This is going to be really valuable once we start traversing these trees.

Lastly,[ there's a way to copy everything we went through in the past month](https://janice.e-351.com/a/R91Q2e), which helps understand our needs at a macro level.

# Inputs

[https://my.minmatar.org/industry/products/](https://my.minmatar.org/industry/products/)

Alright, now that we've got our outputs, we can traverse those fancy trees and start to build out a model of all of the things our alliance needs.

We call these **products**.

A product can be a few things,

* Something we harvest (mining, PI, etc)
* Something we supply (e.g imported goo, refined for pyrite)
* Something we import (raw imports, nothing special here)
* Something we produce and use upstream (e.g Auto Integrity Preservation Seal)

All of these products are categorized and marked. Things start out as imports, but maybe people start to source them locally and be "that" guy for Pyrite.

# ESI Magic

Now the magic happens. Tracking down all these people and figuring this stuff out would be an absolute nightmare- we want to undock and blow things up.

So, how do we automate all of this?

Well, ESI allows us to fetch a few things,

* Personal mining ledger- everything you've mined recently.
* Planet setups- how your planets are set up, what they harvest, and what they make.
* Jobs- what you've been building. Maybe... Auto Integrity Preservation Seals?

Boom. We allow people who are interested to opt-in, because why ask people for ESI scopes that aren't relevant to them, and then we start fetching that data.

Now we can populate who's making what, who's mining what, and who's harvesting what on what planets. If you want to build stuff and need something from them- GO TALK TO THEM! Don't message me!

# Insights

One of our biggest insights was how many people are actually doing planetary interaction, and how much Pyrite it takes to build dreads.

* Allows us to make decisions around importing R4 moon goo for Pyrite
* Allows us to connect PI fanatics with people building dreads in Amamake

Lastly, we can sort suppliers by who harvest the most of something, we can have a good order to message people by.

# Open source

Everything we do is open source. If you want to figure out what we're doing, how we're doing it, and how you can copy it for your alliance, have no fear.

* [Repository](https://github.com/minmatarfleet/minmatar.org)
* [Recent pull requests](https://github.com/minmatarfleet/minmatar.org/pulls?q=is%3Apr+is%3Aclosed)

Want to help us build ships we’ll immediately welp into dread brawls? Swing by.

[https://discord.gg/minmatar](https://discord.gg/minmatar)