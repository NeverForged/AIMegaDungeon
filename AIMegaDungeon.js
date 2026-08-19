/* Helper Function: Safe Handout Display */
function displayHandout(handoutId) {
    if (!handoutId) return;
    // Method 1: Try the popular 'Show Handout' Mod script command via chat
    sendChat("API", "!showhandout " + handoutId);
    // Method 2: Ensure it is shared to player journals so players can view/open it
    let handout = getObj("handout", handoutId);
    if (handout) {
        handout.set("inplayerjournals", "all");
    }
}

/* Helper Function: Convert Basic Markdown & Custom Line Breaks to Roll20-Friendly HTML */
function parseMarkdownToHtml(text) {
    if (!text) return "";
    
    // 1. Replace your custom '|n' marker with actual newlines
    let processed = text.replace(/\|n/g, '\n');
    
    // 2. Escape standard HTML characters to prevent breakdown from malformed user input
    processed = processed
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
        
    // 3. Convert Bold Markdown (**text** or __text__) into <strong> HTML
    processed = processed.replace(/(\*\*|__)(.*?)\1/g, "<strong>$2</strong>");
    
    // 4. Convert Italic Markdown (*text* or _text_) into <em> HTML
    processed = processed.replace(/(\*|_)(.*?)\1/g, "<em>$2</em>");
    
    // 5. Convert standard line breaks into HTML break tags for Roll20's text fields
    processed = processed.replace(/\n/g, "<br>");
    
    // 6. Wrap in a clean div container instead of <pre> to allow natural styling and processing
    return "<div style='font-family: sans-serif; font-size: 14px; line-height: 1.4;'>" + processed + "</div>";
}

/* COMMAND: !map || Room Name or Path || URL || GridW || GridH || Description */
on("chat:message", function(msg) {
    if (msg.type !== "api" || !msg.content.startsWith("!map ")) return;
    sendChat("API", "/w gm [DEBUG !map] Received command.");
    
    let args = msg.content.split("||");
    if (args.length < 6) {
        sendChat("API", "/w gm [DEBUG !map] ERROR: Less than 6 arguments provided.");
        return;
    }
    
    let rawPath = args[1].trim();
    let cleanName = rawPath.split(/[/\\]/).pop().replace(/\.[^/.]+$/, "");
    let url = args[2].trim().split('?')[0].replace("max.png", "thumb.png").replace("max.jpg", "thumb.jpg");
    let gW = parseInt(args[3]) || 10;
    let gH = parseInt(args[4]) || 10;
    
    // Pass description argument through the markdown parser function
    let desc = args[5] ? parseMarkdownToHtml(args[5]) : "";
    let handoutName = "Room Asset: " + cleanName;
    
    // Purge any existing/old handouts with the same name to prevent loading stale art
    let oldHandouts = findObjs({_type: "handout", name: handoutName});
    _.each(oldHandouts, function(obj) {
        obj.remove();
    });
    
    sendChat("API", "/w gm [DEBUG !map] Creating fresh handout: " + handoutName);
    let handout = createObj("handout", {name: handoutName, inplayerjournals: "all"});
    handout.set("avatar", url);
    
    setTimeout(() => {
        handout.set("gmnotes", desc);
        sendChat("API", "/w gm [DEBUG !map] Showing handout (ID: " + handout.id + ")...");
        displayHandout(handout.id);
    }, 200);
    
    // --- PAGE & MAP LOGIC ---
    setTimeout(() => {
        try {
            let pageId = Campaign().get("playerpageid");
            let currentPage = getObj("page", pageId);
            if (!currentPage) {
                sendChat("API", "/w gm [DEBUG !map] ERROR: Active player page not found.");
                return;
            }
            sendChat("API", "/w gm [DEBUG !map] Resizing page and creating map graphic...");
            currentPage.set({name: cleanName, width: gW, height: gH});
            
            let oldMaps = findObjs({_pageid: pageId, _type: "graphic", layer: "map"});
            _.each(oldMaps, (obj) => {
                obj.remove();
            });
            
            createObj("graphic", {
                name: cleanName + "_Map",
                _pageid: pageId,
                imgsrc: url,
                layer: "map",
                left: (gW * 70) / 2,
                top: (gH * 70) / 2,
                width: gW * 70,
                height: gH * 70
            });
            sendChat("API", "/w gm [DEBUG !map] Map setup complete.");
        } catch (err) {
            sendChat("API", "/w gm [DEBUG !map] CATCH ERROR: " + err.message);
        }
    }, 600);
});

/* COMMAND: !handout || Handout Name || Image URL || Description */
on("chat:message", function(msg) {
    if (msg.type !== "api" || !msg.content.startsWith("!handout ")) return;
    sendChat("API", "/w gm [DEBUG !handout] Received command.");
    
    let args = msg.content.split("||");
    if (args.length < 4) {
        sendChat("API", "/w gm [DEBUG !handout] ERROR: Less than 4 arguments provided.");
        return;
    }
    
    let name = args[1].trim();
    let url = args[2].trim().split('?')[0].replace("max.png", "thumb.png").replace("max.jpg", "thumb.jpg");
    
    // Pass description argument through the markdown parser function
    let desc = args[3] ? parseMarkdownToHtml(args[3]) : "";
    let handoutName = "Handout: " + name;
    
    // Purge any existing/old handouts with the same name
    let oldHandouts = findObjs({_type: "handout", name: handoutName});
    _.each(oldHandouts, function(obj) {
        obj.remove();
    });
    
    sendChat("API", "/w gm [DEBUG !handout] Creating fresh handout: " + handoutName);
    let handout = createObj("handout", {name: handoutName, inplayerjournals: "all"});
    handout.set("avatar", url);
    
    setTimeout(() => {
        handout.set("notes", desc);
        sendChat("API", "/w gm [DEBUG !handout] Showing handout (ID: " + handout.id + ")...");
        displayHandout(handout.id);
    }, 200);
});
