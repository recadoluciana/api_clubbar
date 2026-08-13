ALTER TABLE checkout_asaas
  ADD COLUMN pix_payload TEXT NULL AFTER pix_qr_code_id,
  ADD COLUMN pix_encoded_image LONGTEXT NULL AFTER pix_payload,
  ADD COLUMN pix_expiration_date DATETIME NULL AFTER pix_encoded_image;
