# CCGE-148 — Website privacy page denies analytics, but Google Analytics is installed (website repo, not this one)

## Goal
Make https://cottonwoodcontractors.com/privacy/ accurate: it says 'There are no cookies, no analytics and no tracking scripts', and /contact/ says 'No mailing list, no tracking', while the developer confirmed on 2026-11-15 that Google Analytics is installed. The page's own Changes section promises an update when analytics is added. The fix lives in the website's repository.

## Inputs
https://cottonwoodcontractors.com/privacy/,https://cottonwoodcontractors.com/contact/,the website's repository

## Constraints
_None._

## Plan
_None._

## Acceptance Criteria
- [ ] https://cottonwoodcontractors.com/privacy/ no longer contains the sentence 'There are no cookies, no analytics and no tracking scripts' and names Google Analytics, and https://cottonwoodcontractors.com/contact/ no longer contains 'no tracking'; or Google Analytics is removed from every page so the existing text is true.

## Depends on
_None._
