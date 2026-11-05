// Cloudflare Turnstile on the Frappe login form (P52). Does nothing unless the site has a Turnstile key.
$(function () {
	const form = $("form.form-login").first();
	if (!form.length) return;
	frappe.call("helpdesk.turnstile.site_key").then((r) => {
		const key = r.message;
		if (!key) return;
		const box = $('<div class="cf-turnstile-box" style="margin:12px 0"></div>');
		form.find("button[type=submit]").first().before(box);
		let token = "";
		const script = document.createElement("script");
		script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
		script.onload = () =>
			window.turnstile.render(box[0], {
				sitekey: key,
				language: "id",
				callback: (t) => (token = t),
				"expired-callback": () => (token = ""),
			});
		document.head.appendChild(script);

		// every attempt needs a fresh token, so reset the widget after each login call
		const call = login.call;
		login.call = function (args, ...rest) {
			if (args && args.cmd === "login") {
				args["cf-turnstile-response"] = token;
				const done = () => window.turnstile && (window.turnstile.reset(box[0]), (token = ""));
				return call.call(this, args, ...rest).always(done);
			}
			return call.call(this, args, ...rest);
		};
	});
});
