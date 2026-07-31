#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{BufRead, BufReader, Write};
use std::net::{IpAddr, SocketAddr, TcpStream};
use std::time::Duration;

pub const PROTOCOL_VERSION: u32 = 1;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeRequest {
    pub protocol: u32,
    pub command: String,
    pub token: String,
    pub build: String,
    #[serde(flatten)]
    pub payload: BTreeMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BridgeResponse {
    pub ok: bool,
    #[serde(default)]
    pub mode: String,
    #[serde(default)]
    pub features: BTreeSet<String>,
    #[serde(default)]
    pub error: String,
}

#[derive(Debug, Clone)]
pub struct RuntimeBridge {
    address: SocketAddr,
    token: String,
    build: String,
}

impl RuntimeBridge {
    pub fn new(address: SocketAddr, token: String, build: String) -> Result<Self, String> {
        if !address.ip().is_loopback() {
            return Err("UMML runtime bridge only permits loopback addresses".into());
        }
        Ok(Self { address, token, build })
    }

    pub fn hello(&self) -> Result<BridgeResponse, String> {
        self.request("hello", BTreeMap::new())
    }

    pub fn queue_profile(&self, profile: &str) -> Result<BridgeResponse, String> {
        let mut payload = BTreeMap::new();
        payload.insert("profile".into(), serde_json::Value::String(profile.into()));
        self.request("queue_profile", payload)
    }

    pub fn reload_feature(&self, feature: &str) -> Result<BridgeResponse, String> {
        let hello = self.hello()?;
        if !hello.ok || !hello.features.contains(feature) {
            return Err(format!("feature {feature} is not enabled for build {}", self.build));
        }
        let mut payload = BTreeMap::new();
        payload.insert("feature".into(), serde_json::Value::String(feature.into()));
        self.request("reload_feature", payload)
    }

    fn request(
        &self,
        command: &str,
        payload: BTreeMap<String, serde_json::Value>,
    ) -> Result<BridgeResponse, String> {
        let mut stream = TcpStream::connect_timeout(&self.address, Duration::from_secs(2))
            .map_err(|error| error.to_string())?;
        stream
            .set_read_timeout(Some(Duration::from_secs(2)))
            .map_err(|error| error.to_string())?;
        let request = BridgeRequest {
            protocol: PROTOCOL_VERSION,
            command: command.into(),
            token: self.token.clone(),
            build: self.build.clone(),
            payload,
        };
        serde_json::to_writer(&mut stream, &request).map_err(|error| error.to_string())?;
        stream.write_all(b"\n").map_err(|error| error.to_string())?;
        let mut line = String::new();
        BufReader::new(stream)
            .read_line(&mut line)
            .map_err(|error| error.to_string())?;
        serde_json::from_str(&line).map_err(|error| error.to_string())
    }
}

pub fn loopback_address(port: u16) -> SocketAddr {
    SocketAddr::new(IpAddr::V4(std::net::Ipv4Addr::LOCALHOST), port)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn refuses_non_loopback() {
        let address = SocketAddr::new(IpAddr::V4(std::net::Ipv4Addr::new(192, 168, 1, 2)), 1234);
        assert!(RuntimeBridge::new(address, "token".into(), "build".into()).is_err());
    }
}
