// Dimensy Ticketing login page (P63): a brand panel beside the login card (desktop) and short Indonesian texts.
// Lucide icons (the set the Dimensy Ticketing app uses), copied from lucide-static; Frappe's own icons are replaced
const LUCIDE = {
	mail: '<path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"/><rect x="2" y="4" width="20" height="16" rx="2"/>',
	lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
	eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
	"eye-off":
		'<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/>',
};
function lucide(name, cls) {
	return $(
		'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"></svg>'
	)
		.addClass(cls)
		.html(LUCIDE[name]);
}

$(function () {
	if (document.body.dataset.path !== "login") return;
	const section = $(".for-login").first();
	const card = section.find(".login-content").first();
	if (!card.length) return;
	section.find(".page-card-head h4").text("Login");
	section.find(".page-card-subtitle").text("Gunakan akun Dimensy Ticketing Anda.");
	section.find("#login_email").attr("placeholder", "nama@email.com");
	const forgot = $(".for-forgot").first();
	forgot.find(".page-card-head h4").text("Lupa password?");
	forgot.find(".page-card-subtitle").text("Tautan untuk membuat password baru dikirim ke email Anda.");
	forgot.find("input[type=email], input[type=text]").attr("placeholder", "nama@email.com");

	// field icons: Lucide instead of Frappe's; the eye becomes a button of its own (Frappe's handler only swaps its own icon)
	$(".page-card .email-icon").each(function () {
		$(this).replaceWith(lucide("mail", "field-icon email-icon"));
	});
	section.find(".password-icon").replaceWith(lucide("lock", "field-icon password-icon"));
	section.find("#login_password").attr("placeholder", "Masukkan password");
	const input = section.find("#login_password");
	const eye = $('<button type="button" class="dimensy-toggle-password" aria-pressed="false" aria-label="Tampilkan password"></button>').append(lucide("eye"));
	section.find(".toggle-password").replaceWith(eye);
	eye.on("click", function () {
		const show = input.attr("type") === "password";
		input.attr("type", show ? "text" : "password");
		eye.attr("aria-pressed", String(show)).attr("aria-label", show ? "Sembunyikan password" : "Tampilkan password");
		eye.empty().append(lucide(show ? "eye-off" : "eye"));
	});

	// the panel sits in a wrapper of its own: Frappe shows and hides the sections themselves (inline display)
	const panel = $('<aside class="dimensy-login-brand" aria-hidden="true"></aside>');
	panel.append($('<img class="dimensy-login-logo" alt="">').attr("src", "/files/logo-dimensy-trust.png"));
	panel.append($('<p class="dimensy-login-eyebrow"></p>').text("Dimensy Trust"));
	panel.append($("<h2></h2>").text("Dimensy Ticketing"));
	panel.append($('<p class="dimensy-login-lead"></p>').text("Layanan bantuan Dimensy Trust."));
	const shell = $('<div class="dimensy-login-shell"></div>');
	card.before(shell);
	shell.append(panel, card);
});
