/* COMMAND: !map ||Room Name||URL||GridW||GridH||Description */

on("chat:message", function(msg) {
    if (msg.type !== "api" || !msg.content.startsWith("!map ")) return;

    let args = msg.content.split("||");
    if (args.length < 6) return;

    let name = args[1].trim();
    let url  = args[2].trim().split('?')[0].replace("max.png", "thumb.png").replace("max.jpg", "thumb.jpg");
    let gW   = parseInt(args[3]) || 10;
    let gH   = parseInt(args[4]) || 10;
    
    // Wrap the description in <pre> to preserve all spaces and indentations
    // We still replace |n with <br> just in case, but <pre> handles standard newlines too.
    let desc = args[5] ? "<pre style='white-space: pre-wrap; font-family: monospace;'>" + args[5].replace(/\|n/g, '\n') + "</pre>" : "";

    let handoutName = "Room Asset: " + name;
    let handout = findObjs({ _type: "handout", name: handoutName })[0];

    if (!handout) {
        handout = createObj("handout", { name: handoutName, inplayerjournals: "all" });
    }

    handout.set("avatar", url);
    
    setTimeout(() => {
        handout.set("gmnotes", desc);
        sendChat("API", "!showhandout " + handout.id);
    }, 200);

    // --- PAGE & MAP LOGIC ---
    setTimeout(() => {
        try {
            let pageId = Campaign().get("playerpageid");
            let currentPage = getObj("page", pageId);
            if (!currentPage) return;

            currentPage.set({ name: name, width: gW, height: gH });

            let oldMaps = findObjs({ _pageid: pageId, _type: "graphic", layer: "map" });
            _.each(oldMaps, (obj) => { obj.remove(); });

            createObj("graphic", {
                name: name + "_Map",
                _pageid: pageId,
                imgsrc: url,
                layer: "map",
                left: (gW * 70) / 2,
                top: (gH * 70) / 2,
                width: gW * 70, 
                height: gH * 70
            });
        } catch (err) {
            log("API Error: " + err.message);
        }
    }, 600);
});