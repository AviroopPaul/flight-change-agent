# Manual End-to-End Test Plan

Follow these tests on the live site. Every value you need is listed here. You never need to invent a booking, a name or a date.

## Before you start

- **Site:** https://flight-change-agent.vercel.app
- **Browser:** Chrome or Safari on a laptop. Use **headphones**, so the agent does not hear itself.
- **New session per test:** open the site in a new tab with no `?sessionId=` in the URL. The page then makes a fresh session and puts its id in the URL.
- **See the delivered record:** open `https://flight-backend-820256992821.asia-south1.run.app/stub/records?sessionId=<id from the URL>`.
- **Speak naturally, then pause.** The agent waits for a short silence before it answers.

## Seeded bookings

Departure dates move with the day you test. "Today" means the day of the test, in India time.

| PNR | Status | Fare class | Passenger names (type exactly, any case) | Route | Current flight | Fare paid per person | Refund goes to |
|---|---|---|---|---|---|---|---|
| `ABC123` | confirmed | saver (₹3,000 change fee) | `Rahul Sharma` | Bengaluru (BLR) to Delhi (DEL) | today + 5 days, 07:05 | ₹5,400 | Visa •• 4242 |
| `PQR456` | confirmed | saver (₹3,000 change fee per person) | `Ananya Iyer`, `Kartik Iyer` | Mumbai (BOM) to Delhi (DEL) | today + 9 days, 18:40 | ₹6,100 | Mastercard •• 1881 |
| `FLX789` | confirmed | flex (no change fee) | `Meera Nair` | Bengaluru (BLR) to Mumbai (BOM) | today + 12 days, 09:35 | ₹8,900 | UPI •• kotak |
| `CNX111` | cancelled | saver | `Arjun Mehta` | Delhi (DEL) to Kolkata (CCU) | today + 6 days | ₹5,000 | none |
| `OLD222` | confirmed | saver | `Sneha Rao` | Hyderabad (HYD) to Delhi (DEL) | 2 days ago (already flown) | ₹4,900 | none |
| `SON333` | confirmed | saver | `Vikram Singh` | Bengaluru (BLR) to Delhi (DEL) | in 2 hours | ₹5,200 | none |

**Names:** titles and punctuation are ignored, so `Mr. rahul sharma` also works. A name not on the booking is rejected.

**New flights:** every route has flights at **06:10, 09:35** (morning), **13:20** (afternoon), **17:45, 21:05** (evening). One of the five is sold out each day and is never shown. Fares change by date and flight.

**Time-of-day words the agent accepts:** morning (5 am to 12 pm), afternoon (12 pm to 5 pm), evening (5 pm to midnight), any time.

**Dates you can use:** any day from today to 330 days ahead, except the day of the current flight. Saying a full date ("the 20th of December") is safer than "next Friday".

## Tests

Mark each one Pass or Fail, and note the session id for any failure.

### 1. Happy path, voice + chat (expected: `completed`)

1. Open the site. A welcome message shows. Tap the call button.
2. The agent greets you and asks for the reason. Say: **"My work meeting was moved, so I need to change my flight."**
3. The agent asks for the booking reference in the chat. Type **`ABC123`** in the bar at the bottom.
4. The next box asks for the passenger name. Type **`Rahul Sharma`**.
5. An optional email question appears, with a field, **Save** and **Skip** inside it. The agent says you can type it or skip it, then waits: nothing else is asked until you tap **Skip** (or type an email and tap **Save**). Tap **Skip**.
6. When the agent asks for the new date, say: **"The twentieth of December."** It should read the date back.
7. When it asks for the time of day, say: **"Afternoon."**
8. A flight list appears as an agent message (left side). Pick the first option.
9. A fare message shows old fare, new fare, change fee and the total. Tap **Yes**.
10. **Expect:** the agent reads a short summary (with the date in words) and hangs up. The chat shows a "Flight change confirmed" card. The record link above shows the same record, with `contactEmail` skipped (null).

### 2. Two passengers (expected: `completed`)

As test 1, but type **`PQR456`**. Two name boxes appear, one after the other. Type **`Ananya Iyer`** then **`Kartik Iyer`**. Use any valid date and "evening".
**Expect:** the fare total covers 2 passengers (change fee ₹6,000 in total).

### 3. Flex fare gives a refund (expected: `completed` with a refund)

As test 1 with **`FLX789`** and name **`Meera Nair`**. Pick a date and "any time". In the list, pick a flight that says **"refund ₹…"** (it is cheaper than ₹8,900).
**Expect:** the fare box says the refund goes to **UPI •• kotak**. The record's `quote.refundDue` is above 0.

### 4. Bad booking references (expected: an error line under the box each time)

In the booking-reference box, type each value in turn:

| Type | Expected message |
|---|---|
| `AB12` | "That doesn't look right." (the box checks the format before sending) |
| `ZZZ999` | "I can't find a booking with that reference. Please check it." |
| `CNX111` | "That booking is cancelled, so it can't be changed." |
| `OLD222` | "That flight has already left or leaves in under 3 hours, so it can't be changed here." |
| `SON333` | "That flight has already left or leaves in under 3 hours, so it can't be changed here." |
| ` abc 123 ` | accepted as `ABC123` |

### 5. Wrong name (expected: rejected, then accepted)

With `ABC123`: type **`John Doe`**.
**Expect:** "That name doesn't match a passenger on this booking. Please type it exactly as on the ID." It never shows the real name. Then type **`mr. rahul sharma`**. **Expect:** accepted.

### 6. Bad dates

With `ABC123` on the call, try each:

| Say | Expected |
|---|---|
| "Yesterday" | the agent says the date has passed |
| The day of the current flight (today + 5 days) | "That's the same day as your current flight..." |
| A date more than 330 days away | "We can only book up to 330 days ahead." |

### 7. Decline the fare (expected: the list comes back)

Run test 1 up to the fare box and tap **No**.
**Expect:** the flight list appears again. Pick another flight and tap **Yes** to finish.

### 8. Refund instead of a new flight (expected: `needsReview`)

On the call, give a reason, then type `ABC123` and `Rahul Sharma`. Say: **"Actually, I just want a refund instead."**
**Expect:** the agent says a person will process the refund. The record has `outcome: needsReview` and `requestType: refund`.
**Variant:** switch to a refund while the names box is still open, then say "thanks, bye". **Expect:** the agent does not hang up. It asks you to finish the names, and says goodbye only after the record shows.

### 9. Stop with the chat button (expected: `optedOut`)

Start a session. Tap **Stop request** in the header. A box asks "Stop this request? Nothing will be changed." Tap **Yes**.
**Expect:** the record shows `outcome: optedOut`. The chat accepts no more input.

### 10. Stop by voice (expected: `optedOut`)

On the call, say: **"I want to stop this request."** The agent asks you to confirm. Say **"Yes."**
**Expect:** a record with `outcome: optedOut`, and the call ends.

### 11. Chat only, never call (expected: `completed`)

Open a new session and do not tap call. After about 20 seconds the chat starts asking.
Answer: `ABC123`, `Rahul Sharma`, then the reason **"Family wedding"** in the bar, a date (pick it inside the date message and tap **Use date**), **Afternoon**, the first flight, **Yes**. When the email question appears, type one and tap **Save**, or tap **Skip**; the next question comes only after that.
**Expect:** `completed`, with `changeReason.value.category` of `personal`.

### 12. Spoken reference vs typed one (expected: the typed one wins)

On the call, say: **"My booking reference is A B C 1 2 4."** Then type **`ABC123`** in the box.
**Expect:** the session continues with `ABC123`. The final record's `conflicts` lists `pnr` with `resolution: chatValue`.

### 13. Different date on the call and in the chat (expected: you are asked to choose)

Do test 11 up to the date box and pick a date in the chat. Then tap call and say a **different** date.
**Expect:** the agent asks which date is right. Answer it. The record lists the conflict as resolved.
If you hang up without choosing, the chat shows a box with both dates.

### 14. Interrupt the agent (barge-in)

While the agent is speaking a long sentence, start talking.
**Expect:** it stops speaking within about a second and listens.

### 15. Reload during the chat

After answering two boxes, reload the page.
**Expect:** the same session id, your earlier answers in the thread, and the open box shown again.

### 16. Reload during the call

During a call, reload the page and tap call again within 1 minute.
**Expect:** the agent says something like "welcome back" and continues. It does not ask again for what you already gave.

### 17. Leave and come back (expected: `partial`, then revision 2)

Start a session, answer the booking reference only, and close the tab. Wait **at least 35 minutes**.
**Expect:** the record link shows `outcome: partial` at revision 1. Reopen the same URL (with the same `sessionId`) and finish the flow. **Expect:** a new record at revision 2 with `completed`.

### 18. Session limit

From one network, open 11 new sessions within an hour.
**Expect:** the 11th shows "Too many sessions from this network. Try again later."

### 19. New chat

Answer the booking-reference box, then tap the **pencil icon** in the header.
**Expect:** a new session id in the URL and an empty thread with the welcome message. Open the old URL (with the old `sessionId`): your earlier answers are still there.
During a call, tap the pencil icon. **Expect:** a box asks "End the call and start a new chat?". Cancel keeps the call.

## What to send back for a failure

- The session id (from the URL)
- The test number and step
- What you said or typed, and what you saw
