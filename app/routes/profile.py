from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Organization, User
from app.services import photo_service
from app.services.profile_service import (
    can_see_contact, can_view_profile, clean_profile, completeness, shown_values,
)
from app.services.validation import check_password

bp = Blueprint("profile", __name__)


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def edit():
    user = current_user._get_current_object()
    form = None
    if request.method == "POST":
        values, error = clean_profile(request.form)
        if error:
            flash(error)
            form = request.form
        else:
            for key, value in values.items():
                setattr(user, key, value)
            db.session.commit()
            flash("Profile saved.", "ok")
            return redirect(url_for("profile.edit"))

    org = db.session.get(Organization, user.organization_id)
    manager = db.session.get(User, user.manager_id) if user.manager_id else None
    return render_template(
        "profile/edit.html", org=org, manager=manager,
        shown=shown_values(user, form), completeness=completeness(user),
    )


@bp.route("/profile/photo", methods=["POST"])
@login_required
def set_photo():
    file = request.files.get("photo")
    if not file or not file.filename:
        flash("Please choose a photo.")
        return redirect(url_for("profile.edit"))
    try:
        data = photo_service.process_image(file.read(photo_service.MAX_BYTES + 1))
        url, public_id = photo_service.upload_photo(data)
    except photo_service.PhotoError as exc:
        flash(str(exc))
        return redirect(url_for("profile.edit"))

    user = current_user._get_current_object()
    old_id = user.photo_public_id
    user.photo_url, user.photo_public_id = url, public_id
    db.session.commit()
    if old_id:
        photo_service.delete_photo(old_id)
    flash("Photo updated.", "ok")
    return redirect(url_for("profile.edit"))


@bp.route("/profile/photo/remove", methods=["POST"])
@login_required
def remove_photo():
    user = current_user._get_current_object()
    old_id = user.photo_public_id
    user.photo_url = None
    user.photo_public_id = None
    db.session.commit()
    if old_id:
        photo_service.delete_photo(old_id)
    flash("Photo removed.", "ok")
    return redirect(url_for("profile.edit"))


@bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    user = current_user._get_current_object()
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not user.check_password(current):
        flash("Your current password is not correct.")
    elif check_password(new):
        flash(check_password(new))
    elif new != confirm:
        flash("The two new passwords do not match.")
    elif new == current:
        flash("Please choose a password different from your current one.")
    else:
        user.set_password(new)
        db.session.commit()
        flash("Password changed.", "ok")
    return redirect(url_for("profile.edit"))


@bp.route("/people/<int:user_id>")
@login_required
def view(user_id):
    person = User.query.filter_by(
        id=user_id, organization_id=current_user.organization_id
    ).first_or_404()
    if not can_view_profile(current_user, person):
        abort(403)
    manager = db.session.get(User, person.manager_id) if person.manager_id else None
    if manager and not can_view_profile(current_user, manager):
        manager = None
    return render_template(
        "profile/view.html", person=person, manager=manager,
        show_contact=can_see_contact(current_user, person),
        is_self=current_user.id == person.id,
    )