import asyncio
from api.db.db_client import DBClient
from api.utils.auth import hash_password, create_jwt_token, verify_password
from api.services.organization_bootstrap import ensure_organization_bootstrapped

async def main():
    email = "shivaprasad@gmail.com"
    raw_password = "shiva@112"
    name = "Shiva Prasad"
    
    db = DBClient()
    existing_user = await db.get_user_by_email(email)
    if existing_user:
        print(f"User {email} already exists! ID: {existing_user.id}, Org: {existing_user.selected_organization_id}")
        user = existing_user
    else:
        hashed = hash_password(raw_password)
        user = await db.create_user_with_email(
            email=email,
            password_hash=hashed,
            name=name,
        )
        print(f"Created user: {user.id}, provider_id: {user.provider_id}")
        
        org_provider_id = f"org_{user.provider_id}"
        organization, created = await db.get_or_create_organization_by_provider_id(
            org_provider_id=org_provider_id, user_id=user.id
        )
        print(f"Organization: {organization.id}, created: {created}")
        
        await db.add_user_to_organization(user.id, organization.id)
        await db.update_user_selected_organization(user.id, organization.id)
        
        await ensure_organization_bootstrapped(
            organization.id,
            created_by=user.provider_id,
        )
        print("Bootstrapped organization successfully.")
    
    # Verify login & password verification
    user_check = await db.get_user_by_email(email)
    assert verify_password(raw_password, user_check.password_hash)
    token = create_jwt_token(user_check.id, email)
    print("SUCCESS: User verified. JWT token generated.")
    print("User ID:", user_check.id)
    print("Selected Org ID:", user_check.selected_organization_id)

if __name__ == "__main__":
    asyncio.run(main())

